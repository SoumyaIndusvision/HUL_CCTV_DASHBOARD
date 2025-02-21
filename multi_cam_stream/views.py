import os
import cv2
import time
import signal
import logging
import asyncio
import numpy as np
import subprocess
import multiprocessing as mp
from django.http import StreamingHttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Seracs, Section, Camera
from .serializers import SeracSerializer, SectionSerializer, CameraSerializer

from .tasks import stream_camera_ffmpeg
from django.core.cache import cache

logger = logging.getLogger(__name__)

class SeracsViewSet(viewsets.ViewSet):
    """
    A ViewSet for managing Serac divisions.
    """
    @swagger_auto_schema(
        operation_summary="List all Seracs",
        operation_description="Fetches all Seracs. This endpoint returns a list of all Seracs available in the system.",
        responses={
            200: openapi.Response(
                description="List of all Seracs",
                examples={
                    "application/json": {
                        "results": [
                            {
                                "id": 1,
                                "name": "Serac 1",
                                "description": "Description for Serac 1"
                            },
                            {
                                "id": 2,
                                "name": "Serac 2",
                                "description": "Description for Serac 2"
                            }
                        ],
                        "status": "200 OK"
                    }
                }
            )
        }
    )
    def list(self, request):
        seracs = Seracs.objects.all()
        serializer = SeracSerializer(seracs, many=True)
        return Response({"results": serializer.data, "status": status.HTTP_200_OK})


    @swagger_auto_schema(
        operation_summary="Retrieve a specific Serac",
        operation_description="Fetches a specific Serac by its primary key (pk). If the Serac is not found, a 404 Not Found error is returned.",
        responses={
            200: openapi.Response(
                description="Serac retrieved successfully",
                examples={
                    "application/json": {
                        "results": {
                            "id": 1,
                            "name": "Serac 1",
                            "description": "Description for Serac 1"
                        },
                        "status": "200 OK"
                    }
                }
            ),
            404: openapi.Response(
                description="Serac not found",
                examples={
                    "application/json": {
                        "message": "Serac not found",
                        "status": "404 Not Found"
                    }
                }
            )
        }
    )
    def retrieve(self, request, pk=None):
        try:
            serac = Seracs.objects.get(pk=pk)
            serializer = SeracSerializer(serac)
            return Response({"results": serializer.data, "status": status.HTTP_200_OK})
        except Seracs.DoesNotExist:
            return Response({"message": "Serac not found", "status": status.HTTP_404_NOT_FOUND})


    @swagger_auto_schema(
        operation_summary="Create a new Serac",
        operation_description="Creates a new Serac using the provided data. The data should be validated according to the SeracSerializer.",
        request_body=SeracSerializer,
        responses={
            201: openapi.Response(
                description="Serac created successfully",
                examples={
                    "application/json": {
                        "message": "Serac created",
                        "status": "201 Created"
                    }
                }
            ),
            400: openapi.Response(
                description="Bad Request if the data provided is invalid",
                examples={
                    "application/json": {
                        "message": "Invalid data",
                        "errors": {
                            "name": ["This field is required."],
                            "description": ["This field is required."]
                        }
                    }
                }
            )
        }
    )
    def create(self, request):
        serializer = SeracSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Serac created", "status": status.HTTP_201_CREATED})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class SectionViewSet(viewsets.ViewSet):
    """
    A ViewSet for managing Sections within a Serac.
    """
    @swagger_auto_schema(
        operation_summary="List all sections for a Serac, including associated camera IDs",
        operation_description=(
            "Fetches all sections for the specified Serac ID along with their associated camera IDs. "
            "If `serac_id` is not provided, it returns a `400 Bad Request` error."
        ),
        manual_parameters=[
            openapi.Parameter(
                name="serac_id",
                in_=openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                description="ID of the Serac to retrieve sections for",
                required=True
            )
        ],
        responses={
            200: openapi.Response(
                description="A list of sections with associated camera IDs",
                examples={
                    "application/json": {
                        "results": [
                            {
                                "id": 1,
                                "name": "Section 1",
                                "serac_id": 1,
                                "camera_ids": [1, 2, 3]
                            },
                            {
                                "id": 2,
                                "name": "Section 2",
                                "serac_id": 1,
                                "camera_ids": [4, 5]
                            }
                        ],
                        "status": "200 OK"
                    }
                }
            ),
            400: openapi.Response(
                description="Bad Request if `serac_id` is not provided",
                examples={
                    "application/json": {
                        "message": "serac_id is required"
                    }
                }
            ),
            404: openapi.Response(
                description="Not Found if Serac does not exist"
            )
        }
    )
    def list(self, request):
        serac_id = request.query_params.get('serac_id')

        if not serac_id:
            return Response(
                {"message": "serac_id is required", "status": status.HTTP_400_BAD_REQUEST}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            serac = Seracs.objects.get(id=serac_id)
        except Seracs.DoesNotExist:
            return Response(
                {"message": "Serac not found", "status": status.HTTP_404_NOT_FOUND}, 
                status=status.HTTP_404_NOT_FOUND
            )

        sections = Section.objects.filter(serac_id=serac_id).prefetch_related('cameras')

        results = []
        for section in sections:
            camera_ids = list(section.cameras.values_list('id', flat=True))  # Fetch camera IDs
            results.append({
                "id": section.id,
                "name": section.name,
                "serac": section.serac_id,
                "camera_ids": camera_ids  # Add camera_ids to response
            })

        return Response({"results": results, "status": status.HTTP_200_OK})

    @swagger_auto_schema(
        operation_summary="Retrieve a specific Section",
        operation_description="Fetches a specific section by its primary key (pk). If the section is not found, a 404 Not Found error will be returned.",
        responses={
            200: openapi.Response(
                description="Section retrieved successfully",
                examples={
                    "application/json": {
                        "results": {
                            "id": 1,
                            "name": "Section 1",
                            "serac_id": 1
                        },
                        "status": "200 OK"
                    }
                }
            ),
            404: openapi.Response(
                description="Section not found",
                examples={
                    "application/json": {
                        "message": "Section not found",
                        "status": "404 Not Found"
                    }
                }
            )
        }
    )
    def retrieve(self, request, pk=None):
        try:
            section = Section.objects.get(pk=pk)
            serializer = SectionSerializer(section)
            return Response({"results": serializer.data, "status": status.HTTP_200_OK})
        except Section.DoesNotExist:
            return Response({"message": "Section not found", "status": status.HTTP_404_NOT_FOUND})


    @swagger_auto_schema(
        operation_summary="Create a new Section",
        operation_description=(
            "Creates a new section using the provided data. The data should match the "
            "structure defined by the SectionSerializer. If the data is valid, a new section is created."
        ),
        request_body=SectionSerializer,
        responses={
            201: openapi.Response(
                description="Section created successfully",
                examples={
                    "application/json": {
                        "message": "Section created",
                        "status": "201 Created"
                    }
                }
            ),
            400: openapi.Response(
                description="Bad Request if the data provided is invalid",
                examples={
                    "application/json": {
                        "message": "Invalid data",
                        "errors": {
                            "name": ["This field is required."],
                            "serac_id": ["This field must be a valid integer."]
                        }
                    }
                }
            )
        }
    )
    def create(self, request):
        serializer = SectionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Section created", "status": status.HTTP_201_CREATED})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CameraViewSet(viewsets.ViewSet):
    """
    A ViewSet for managing Cameras within Sections.
    """
    @swagger_auto_schema(
        operation_summary="List all cameras for a given section or all cameras if `section_id` is not provided",
        operation_description=(
            "Fetches all cameras for the specified Section ID if `section_id` is provided. "
            "If no `section_id` is provided, all cameras will be returned."
        ),
        manual_parameters=[
            openapi.Parameter(
                name="section_id", 
                in_=openapi.IN_QUERY, 
                type=openapi.TYPE_INTEGER, 
                description="ID of the section to retrieve cameras for",
                required=True
            )
        ],
        responses={
            200: openapi.Response(
                description="A list of cameras",
                examples={
                    "application/json": {
                        "results": [
                            {
                                "id": 1,
                                "name": "Camera 1",
                                "section_id": 1
                            },
                            {
                                "id": 2,
                                "name": "Camera 2",
                                "section_id": 1
                            }
                        ],
                        "status": "200 OK"
                    }
                }
            ),
            400: openapi.Response(
                description="Bad Request if invalid query parameter",
                examples={
                    "application/json": {
                        "message": "Invalid section_id"
                    }
                }
            )
        }
    )
    def list(self, request):
        section_id = request.query_params.get('section_id')
        
        if section_id:
            cameras = Camera.objects.filter(section_id=section_id)
        else:
            cameras = Camera.objects.all()

        serializer = CameraSerializer(cameras, many=True)
        return Response({"results": serializer.data, "status": status.HTTP_200_OK})

    @swagger_auto_schema(
        operation_summary="Retrieve a specific camera",
        operation_description="Fetches details of a specific camera by its unique ID.",
        responses={
            200: openapi.Response(
                description="Details of the specified camera",
                examples={
                    "application/json": {
                        "results": {
                            "id": 1,
                            "name": "Camera 1",
                            "section_id": 1
                        },
                        "status": "200 OK"
                    }
                }
            ),
            404: openapi.Response(
                description="Not Found if the camera with the specified ID does not exist",
                examples={
                    "application/json": {
                        "message": "Camera not found"
                    }
                }
            )
        }
    )
    def retrieve(self, request, pk=None):
        try:
            camera = Camera.objects.get(pk=pk)
        except Camera.DoesNotExist:
            return Response(
                {"message": "Camera not found", "status": status.HTTP_404_NOT_FOUND}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = CameraSerializer(camera)
        return Response({"results": serializer.data, "status": status.HTTP_200_OK})

    @swagger_auto_schema(
        operation_summary="Create a new camera",
        operation_description=(
            "Creates a new camera entry using the provided data. "
            "The data should be in the format expected by the CameraSerializer. "
            "If the data is valid, a new camera is created and a success message is returned."
        ),
        request_body=CameraSerializer,
        responses={
            201: openapi.Response(
                description="Camera created successfully",
                examples={
                    "application/json": {
                        "message": "Camera created",
                        "status": "201 Created"
                    }
                }
            ),
            400: openapi.Response(
                description="Bad Request if the data provided is invalid",
                examples={
                    "application/json": {
                        "message": "Invalid data",
                        "errors": {
                            "name": ["This field is required."],
                            "section_id": ["This field must be a valid integer."]
                        }
                    }
                }
            )
        }
    )
    def create(self, request):
        serializer = CameraSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Camera created", "status": status.HTTP_201_CREATED})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

REDIS_FRAME_KEY = "camera_stream:{camera_id}"

def generate_frames(camera_id):
    """Yield latest frames for HTTP streaming."""
    while True:
        frame = cache.get(REDIS_FRAME_KEY.format(camera_id=camera_id))
        if frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n'
                   b'Content-Length: ' + f"{len(frame)}".encode() + b'\r\n'
                   b'\r\n' + frame + b'\r\n')
        else:
            time.sleep(0.5)

def video_feed(request, camera_id):
    """Django view for video streaming."""
    camera = get_object_or_404(Camera, id=camera_id)

    # Ensure only cameras from the active section are running
    current_section = cache.get("active_section")
    if current_section != camera.section.id:
        return JsonResponse({"error": "Camera is not part of the active section"}, status=403)

    # Start the Celery task if not already running
    if not cache.get(f"camera_active:{camera_id}"):
        stream_camera_ffmpeg.delay(camera.id, camera.get_rtsp_url(), camera.section.id)
        cache.set(f"camera_active:{camera_id}", True, timeout=60)

    return StreamingHttpResponse(generate_frames(camera_id), content_type='multipart/x-mixed-replace; boundary=frame')


class MultiCameraStreamViewSet(viewsets.ViewSet):
    """API View for multi-camera streaming."""

    def retrieve(self, request, pk=None):
        section = get_object_or_404(Section, id=pk)
        cameras = Camera.objects.filter(section=section, is_active=True)
        active_stream_urls = {}

        # Check currently active section
        previous_section = cache.get("active_section")

        # If the section has changed, terminate all previous section cameras
        if previous_section and previous_section != pk:
            previous_cameras = Camera.objects.filter(section_id=previous_section, is_active=True)
            for camera in previous_cameras:
                cache.delete(f"camera_active:{camera.id}")  # Remove active flag
            cache.set("active_section", pk, timeout=60)

        # Start streams for the current section
        for camera in cameras:
            active_stream_urls[camera.id] = f"/api/video_feed/{camera.id}/"
            if not cache.get(f"camera_active:{camera.id}"):
                stream_camera_ffmpeg.delay(camera.id, camera.get_rtsp_url(), pk)
                cache.set(f"camera_active:{camera.id}", True, timeout=60)

        return JsonResponse({"message": "Camera feeds", "streams": active_stream_urls}, status=status.HTTP_200_OK)


###################################################################################################################################3

# # Constants
# MAX_CONCURRENT_STREAMS = 30
# FRAME_TIMEOUT = 60  # Camera timeout in seconds

# # Global Shared State (Using Manager)
# manager = mp.Manager()
# frame_buffers = manager.dict()  # {camera_id: Manager().list()}
# active_streams = manager.dict()  # {camera_id: process_pid}

# logger = logging.getLogger(__name__)

# # -----------------------------------------
# # ASYNC FUNCTION: Initialize All Camera Streams
# # -----------------------------------------
# async def async_initialize_all_camera_streams():
#     """Asynchronously fetches and starts all active camera streams."""
#     logger.info("Initializing all camera streams asynchronously...")
    
#     active_cameras = await asyncio.to_thread(lambda: list(Camera.objects.filter(is_active=True).order_by("id")))

#     for camera in active_cameras:
#         if camera.id not in active_streams:
#             await asyncio.to_thread(start_camera_process, camera.id, camera.get_rtsp_url())

#     logger.info("All camera streams initialized.")

# # -----------------------------------------
# # MULTIPROCESS FUNCTION: Start Camera Stream
# # -----------------------------------------
# def start_camera_process(camera_id, camera_url):
#     """Spawns a new process for handling a camera stream if not already running."""
#     if camera_id in active_streams:
#         return  # Process already running
    
#     process = mp.Process(target=stream_camera_ffmpeg, args=(camera_id, camera_url, frame_buffers))
#     process.daemon = True  # Allows process cleanup on exit
#     process.start()
#     active_streams[camera_id] = process.pid  # Store process ID

# # -----------------------------------------
# # MULTIPROCESS FUNCTION: Stream Camera using FFmpeg
# # -----------------------------------------
# def stream_camera_ffmpeg(camera_id, camera_url, frame_buffers):
#     """Starts an FFmpeg process for a camera and maintains the frame queue."""
#     logger.info(f"Starting stream for camera {camera_id} at {camera_url}")

#     frame_buffers[camera_id] = manager.list()  # Shared memory list

#     try:
#         ffmpeg_cmd = [
#             "ffmpeg", "-rtsp_transport", "tcp", "-i", camera_url,
#             "-an", "-vf", "fps=5,scale=640:480", "-f", "image2pipe",
#             "-pix_fmt", "bgr24", "-vcodec", "rawvideo", "-"
#         ]
#         process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8)
#         active_streams[camera_id] = process.pid  # Store PID
#         frame_size = 640 * 480 * 3
#         last_frame_time = time.time()

#         while True:
#             raw_frame = process.stdout.read(frame_size)

#             if len(raw_frame) != frame_size:
#                 if time.time() - last_frame_time > FRAME_TIMEOUT:
#                     logger.warning(f"Camera {camera_id} unresponsive. Restarting...")
#                     restart_camera_stream(camera_id)
#                     return  
#                 continue

#             frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((480, 640, 3))
#             _, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])

#             if len(frame_buffers[camera_id]) >= 60:
#                 frame_buffers[camera_id].pop(0)  # Remove old frame
            
#             frame_buffers[camera_id].append(jpeg.tobytes())
#             last_frame_time = time.time()

#     except Exception as e:
#         logger.error(f"Error in stream for camera {camera_id}: {e}")
#         restart_camera_stream(camera_id)

#     finally:
#         cleanup_camera_stream(camera_id)

# # -----------------------------------------
# # FUNCTION: Cleanup Camera Process
# # -----------------------------------------
# def cleanup_camera_stream(camera_id):
#     """Stops the camera process and removes buffers."""
#     if camera_id in active_streams:
#         pid = active_streams[camera_id]
#         try:
#             os.kill(pid, signal.SIGTERM)  # Graceful termination
#         except ProcessLookupError:
#             pass  # Process already terminated
        
#         del active_streams[camera_id]

#     if camera_id in frame_buffers:
#         del frame_buffers[camera_id]

#     logger.info(f"Camera {camera_id} process cleaned up.")

# # -----------------------------------------
# # FUNCTION: Cleanup All Streams
# # -----------------------------------------
# def cleanup_all_streams(*args):
#     """Terminates all active camera processes on shutdown."""
#     logger.info("Shutting down all camera streams...")
#     for camera_id in list(active_streams.keys()):
#         cleanup_camera_stream(camera_id)
#     logger.info("All camera processes terminated.")
#     exit(0)

# # Register cleanup function on exit
# signal.signal(signal.SIGINT, cleanup_all_streams)
# signal.signal(signal.SIGTERM, cleanup_all_streams)

# # -----------------------------------------
# # FUNCTION: Restart Camera Process
# # -----------------------------------------
# def restart_camera_stream(camera_id):
#     """Restarts a camera stream after failure."""
#     logger.info(f"Restarting camera {camera_id}...")
#     time.sleep(2)  
#     camera = Camera.objects.filter(id=camera_id).first()
    
#     if camera:
#         start_camera_process(camera.id, camera.get_rtsp_url())

# # -----------------------------------------
# # FUNCTION: Generate Video Feed Frames
# # -----------------------------------------
# def generate_frames(camera_id):
#     """Yields latest frames for HTTP streaming."""
#     while True:
#         if camera_id in frame_buffers and frame_buffers[camera_id]:
#             try:
#                 frame = frame_buffers[camera_id][-1]  # Get the latest frame
#                 yield (b'--frame\r\n'
#                        b'Content-Type: image/jpeg\r\n'
#                        b'Content-Length: ' + f"{len(frame)}".encode() + b'\r\n'
#                        b'\r\n' + frame + b'\r\n')
#             except IndexError:
#                 yield (b'--frame\r\n'
#                        b'Content-Type: image/jpeg\r\n'
#                        b'\r\n' + get_blank_frame() + b'\r\n')
#         else:
#             time.sleep(0.5)

# # -----------------------------------------
# # DJANGO VIEW: Serve Video Feed
# # -----------------------------------------
# def video_feed(request, camera_id):
#     """Django view for optimized video streaming."""
#     camera = get_object_or_404(Camera, id=camera_id)

#     if camera_id not in active_streams:
#         start_camera_process(camera.id, camera.get_rtsp_url())

#     return StreamingHttpResponse(generate_frames(camera_id), content_type='multipart/x-mixed-replace; boundary=frame')

# # -----------------------------------------
# # FUNCTION: Blank Frame For Cameras
# # -----------------------------------------
# def get_blank_frame():
#     """Returns a blank black frame encoded as JPEG."""
#     blank_image = np.zeros((480, 640, 3), dtype=np.uint8)  # Black image (480x640)
#     _, jpeg = cv2.imencode(".jpg", blank_image, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
#     return jpeg.tobytes()

# class MultiCameraStreamViewSet(viewsets.ViewSet):
#     """Handles multi-camera streaming for sections."""
#     @swagger_auto_schema(
#         operation_summary="Retrieve Active Camera Streams for a Section",
#         operation_description="Fetches and returns active camera streams for the specified section.",
#         responses={ 
#             200: openapi.Response(
#                 description="Returns a list of active camera streams for a specified.",
#                 examples={ 
#                     "application/json": { 
#                         "streams": { 
#                             "1": "/api/video_feed/1/", 
#                             "2": "/api/video_feed/2/" 
#                         } 
#                     }
#                 }
#             ),
#             400: openapi.Response(description="Invalid section ID."),
#             404: openapi.Response(description="Section not found."),
#             503: openapi.Response(description="No active cameras found."),
#         }
#     )
#     def retrieve(self, request, pk=None):
#         section = get_object_or_404(Section, id=pk)
#         cameras = Camera.objects.filter(section=section, is_active=True)
#         active_stream_urls = {}

#         for camera in cameras:
#             if camera.id not in active_streams:
#                 start_camera_process(camera.id, camera.get_rtsp_url())

#             active_stream_urls[camera.id] = f"/api/video_feed/{camera.id}/"

#         return JsonResponse({"message": "Camera feeds", "streams": active_stream_urls}, status=status.HTTP_200_OK)
    
# # -----------------------------------------
# # STARTUP: Run Async Initialization
# # -----------------------------------------
# asyncio.run(async_initialize_all_camera_streams())


############################################################################################################################################################
    
# # Constants
# MAX_CONCURRENT_STREAMS = 15
# FRAME_TIMEOUT = 60  # Unresponsive threshold in seconds

# # Global Shared State (Using Manager)
# manager = mp.Manager()
# frame_buffers = manager.dict()  # {camera_id: Manager().list()}
# active_streams = manager.dict()  # {camera_id: process}

# logger = logging.getLogger(__name__)

# def stream_camera_ffmpeg(camera_id, camera_url, frame_buffers):
#     """Starts FFmpeg process for a camera and maintains frame queue."""
#     logger.info(f"Starting stream for camera {camera_id} at {camera_url}")

#     frame_buffers[camera_id] = manager.list()  # Store as Manager list
    
#     try:
#         ffmpeg_cmd = [
#             "ffmpeg", "-rtsp_transport", "tcp", "-i", camera_url,
#             "-an", "-vf", "fps=5,scale=640:480", "-f", "image2pipe",
#             "-pix_fmt", "bgr24", "-vcodec", "rawvideo", "-"
#         ]
#         process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8)
#         active_streams[camera_id] = process.pid  # Store only process PID
#         frame_size = 640 * 480 * 3
#         last_frame_time = time.time()

#         while True:
#             raw_frame = process.stdout.read(frame_size)
            
#             if len(raw_frame) != frame_size:
#                 if time.time() - last_frame_time > FRAME_TIMEOUT:
#                     logger.warning(f"Camera {camera_id} unresponsive for {FRAME_TIMEOUT} seconds. Terminating process.")
#                     cleanup_camera_stream(camera_id)
#                     return  
#                 continue

#             # Process frame
#             frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((480, 640, 3))
#             _, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])

#             # Add frame to buffer (limit to 60 frames)
#             if len(frame_buffers[camera_id]) >= 60:
#                 frame_buffers[camera_id].pop(0)  # Remove old frame
            
#             frame_buffers[camera_id].append(jpeg.tobytes())
#             last_frame_time = time.time()

#     except subprocess.CalledProcessError as e:
#         logger.error(f"FFmpeg subprocess error for camera {camera_id}: {e}")
#     except Exception as e:
#         logger.error(f"Unexpected error for camera {camera_id}: {e}")
#     finally:
#         cleanup_camera_stream(camera_id)

# def cleanup_camera_stream(camera_id):
#     """Cleans up process and removes camera if unresponsive."""
#     if camera_id in active_streams:
#         pid = active_streams[camera_id]
#         subprocess.call(["kill", "-9", str(pid)])  # Kill process by PID
#         del active_streams[camera_id]
    
#     if camera_id in frame_buffers:
#         del frame_buffers[camera_id]
    
#     logger.info(f"Camera {camera_id} has been removed due to unresponsiveness.")

# def generate_frames(camera_id):
#     """Yields latest frames for HTTP streaming."""
#     while True:
#         if camera_id in frame_buffers and frame_buffers[camera_id]:
#             frame = frame_buffers[camera_id][-1]  # Get the latest frame
#             yield (b'--frame\r\n'
#                    b'Content-Type: image/jpeg\r\n'
#                    b'Content-Length: ' + f"{len(frame)}".encode() + b'\r\n'
#                    b'\r\n' + frame + b'\r\n')
#         else:
#             time.sleep(0.5)  

# def initialize_all_camera_streams():
#     """Starts multiprocessing for all active cameras on server startup."""
#     logger.info("Initializing all active camera streams...")

#     # Fetch all active cameras at once
#     active_cameras = Camera.objects.filter(is_active=True).order_by("id")

#     for camera in active_cameras:
#         if camera.id not in active_streams:
#             process = mp.Process(target=stream_camera_ffmpeg, args=(camera.id, camera.get_rtsp_url(), frame_buffers))
#             process.start()
#             active_streams[camera.id] = process.pid  # Store process ID

#     logger.info("All camera streams initialized.")

# def video_feed(request, camera_id):
#     """Django view for optimized video streaming."""
#     camera = get_object_or_404(Camera, id=camera_id)

#     if camera_id not in active_streams:
#         process = mp.Process(target=stream_camera_ffmpeg, args=(camera.id, camera.get_rtsp_url(), frame_buffers))
#         process.start()
#         active_streams[camera_id] = process.pid  # Store process ID

#     return StreamingHttpResponse(generate_frames(camera_id), content_type='multipart/x-mixed-replace; boundary=frame')

# class MultiCameraStreamViewSet(viewsets.ViewSet):
#     """Handles multi-camera streaming for sections."""
#     @swagger_auto_schema(
#         operation_summary="Retrieve Active Camera Streams for a Section",
#         operation_description="Fetches and returns active camera streams for the specified section.",
#         responses={ 
#             200: openapi.Response(
#                 description="Returns a list of active camera streams for a specified.",
#                 examples={ 
#                     "application/json": { 
#                         "streams": { 
#                             "1": "/api/video_feed/1/", 
#                             "2": "/api/video_feed/2/" 
#                         } 
#                     }
#                 }
#             ),
#             400: openapi.Response(description="Invalid section ID."),
#             404: openapi.Response(description="Section not found."),
#             503: openapi.Response(description="No active cameras found."),
#         }
#     )
#     def retrieve(self, request, pk=None):
#         section = get_object_or_404(Section, id=pk)
#         cameras = Camera.objects.filter(section=section, is_active=True)
#         active_stream_urls = {}

#         for camera in cameras:
#             if camera.id not in active_streams:
#                 process = mp.Process(target=stream_camera_ffmpeg, args=(camera.id, camera.get_rtsp_url(), frame_buffers))
#                 process.start()
#                 active_streams[camera.id] = process.pid  

#             active_stream_urls[camera.id] = f"/api/video_feed/{camera.id}/"

#         return JsonResponse({"message": "All camera feeds", "streams": active_stream_urls}, status=status.HTTP_200_OK)
    
# startup_process = mp.Process(target=initialize_all_camera_streams)
# startup_process.start()

########################################################################################################################################################
    
# # Constants
# MAX_CONCURRENT_STREAMS = 15
# FRAME_TIMEOUT = 60  # Mark as unresponsive after 60 seconds

# # Global Shared State
# manager = mp.Manager()
# active_streams = {}  # {camera_id: process}
# frame_buffers = manager.dict()  # {camera_id: deque}

# def stream_camera_ffmpeg(camera_id, camera_url, frame_buffers):
#     """Starts FFmpeg process for a camera and maintains frame queue."""
#     logger.info(f"Starting stream for camera {camera_id} at {camera_url}")

#     frame_buffers[camera_id] = deque(maxlen=60)
    
#     try:
#         ffmpeg_cmd = [
#             "ffmpeg", "-rtsp_transport", "tcp", "-i", camera_url,
#             "-an", "-vf", "fps=5,scale=640:480", "-f", "image2pipe",
#             "-pix_fmt", "bgr24", "-vcodec", "rawvideo", "-"
#         ]
#         process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8)
#         active_streams[camera_id] = process  # Track process
#         frame_size = 640 * 480 * 3
#         last_frame_time = time.time()

#         while True:
#             raw_frame = process.stdout.read(frame_size)
            
#             if len(raw_frame) != frame_size:
#                 # Check if unresponsive
#                 if time.time() - last_frame_time > FRAME_TIMEOUT:
#                     logger.warning(f"Camera {camera_id} unresponsive for {FRAME_TIMEOUT} seconds. Terminating process.")
#                     cleanup_camera_stream(camera_id)
#                     return  # Exit process
#                 continue

#             # Process frame
#             frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((480, 640, 3))
#             _, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
#             frame_buffers[camera_id].append(jpeg.tobytes())

#             last_frame_time = time.time()  # Reset timeout on successful frame

#     except subprocess.CalledProcessError as e:
#         logger.error(f"FFmpeg subprocess error for camera {camera_id}: {e}")
#     except Exception as e:
#         logger.error(f"Unexpected error for camera {camera_id}: {e}")
#     finally:
#         cleanup_camera_stream(camera_id)

# def cleanup_camera_stream(camera_id):
#     """Cleans up process and removes camera if unresponsive."""
#     if camera_id in active_streams:
#         process = active_streams[camera_id]
#         process.kill()
#         del active_streams[camera_id]
    
#     if camera_id in frame_buffers:
#         del frame_buffers[camera_id]
    
#     logger.info(f"Camera {camera_id} has been removed due to unresponsiveness.")

# def generate_frames(camera_id):
#     """Yields latest frames for HTTP streaming."""
#     while True:
#         if camera_id in frame_buffers and frame_buffers[camera_id]:
#             frame = frame_buffers[camera_id][-1]
#             yield (b'--frame\r\n'
#                    b'Content-Type: image/jpeg\r\n'
#                    b'Content-Length: ' + f"{len(frame)}".encode() + b'\r\n'
#                    b'\r\n' + frame + b'\r\n')
#         else:
#             time.sleep(0.5)  # Prevent excessive looping if no frames are available

# def initialize_all_camera_streams():
#     """Starts multiprocessing for all active cameras on server startup."""
#     logger.info("Initializing all active camera streams...")
#     for section in Section.objects.all().order_by("id"):
#         for camera in Camera.objects.filter(section=section, is_active=True).order_by("id"):
#             if camera.id not in active_streams:
#                 process = mp.Process(target=stream_camera_ffmpeg, args=(camera.id, camera.get_rtsp_url(), frame_buffers))
#                 process.start()
#                 active_streams[camera.id] = process

#     logger.info("All active camera streams initialized.")

# def video_feed(request, camera_id):
#     """Django view for video streaming."""
#     camera = get_object_or_404(Camera, id=camera_id)

#     if camera_id not in active_streams:
#         process = mp.Process(target=stream_camera_ffmpeg, args=(camera.id, camera.get_rtsp_url(), frame_buffers))
#         process.start()
#         active_streams[camera_id] = process

#     return StreamingHttpResponse(generate_frames(camera_id), content_type='multipart/x-mixed-replace; boundary=frame')

# class MultiCameraStreamViewSet(viewsets.ViewSet):
#     """Handles multi-camera streaming for sections."""
#     def retrieve(self, request, pk=None):
#         section = get_object_or_404(Section, id=pk)
#         cameras = Camera.objects.filter(section=section, is_active=True)
#         active_stream_urls = {}

#         for camera in cameras:
#             if camera.id not in active_streams:
#                 process = mp.Process(target=stream_camera_ffmpeg, args=(camera.id, camera.get_rtsp_url(), frame_buffers))
#                 process.start()
#                 active_streams[camera.id] = process
#             active_stream_urls[camera.id] = f"/api/video_feed/{camera.id}/"

#         return JsonResponse({"message": "All active camera feeds", "streams": active_stream_urls}, status=status.HTTP_200_OK)

# # Run the initialization function on startup
# startup_process = mp.Process(target=initialize_all_camera_streams)
# startup_process.start()

#############################################################################################################

# # Constants
# MAX_CONCURRENT_STREAMS = 15
# FRAME_TIMEOUT = 20

# # Global Shared State using multiprocessing.Manager
# manager = mp.Manager()
# active_streams = {}  # {camera_id: process} (store locally in the main process)
# frame_buffers = manager.dict()  # {camera_id: deque}
# unresponsive_cameras = manager.list()  # {camera_id list}
# frame_locks = {}  # Store mp.Condition() in a local dictionary

# def stream_camera_ffmpeg(camera_id, camera_url, frame_buffers, unresponsive_cameras):
#     """Starts FFmpeg process for a camera and maintains frame queue."""
#     logger.debug(f"Starting stream for camera {camera_id} at {camera_url}")

#     # Local Condition object (Not in Manager, avoids pickling issues)
#     frame_lock = mp.Condition()

#     frame_buffers[camera_id] = deque(maxlen=30)
    
#     try:
#         ffmpeg_cmd = [
#             "ffmpeg", "-rtsp_transport", "tcp", "-i", camera_url,
#             "-an", "-vf", "fps=7,scale=640:480", "-f", "image2pipe",
#             "-pix_fmt", "bgr24", "-vcodec", "rawvideo", "-"
#         ]
#         process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8)
#         frame_size = 640 * 480 * 3
#         start_time = time.time()

#         while True:
#             raw_frame = process.stdout.read(frame_size)
#             if len(raw_frame) != frame_size:
#                 if time.time() - start_time > FRAME_TIMEOUT:
#                     logger.error(f"Camera {camera_id} unresponsive. Stream will not restart.")
#                     if camera_id not in list(unresponsive_cameras):
#                         unresponsive_cameras.append(camera_id)
#                     break
#                 continue

#             frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((480, 640, 3))
#             _, jpeg = cv2.imencode(".jpg", frame)
#             frame_buffers[camera_id].append(jpeg.tobytes())

#             with frame_lock:
#                 frame_lock.notify_all()

#             start_time = time.time()

#     except Exception as e:
#         logger.error(f"FFmpeg error for camera {camera_id}: {e}")
#     finally:
#         cleanup_camera_stream(camera_id)

# def cleanup_camera_stream(camera_id):
#     """Cleans up FFmpeg process and frame buffer when a stream stops."""
#     if camera_id in active_streams:
#         active_streams[camera_id].kill()
#         del active_streams[camera_id]
#     if camera_id in frame_buffers:
#         del frame_buffers[camera_id]
#     logger.debug(f"Cleaned up stream resources for camera {camera_id}")

# def generate_frames(camera_id):
#     """Yields latest frames for efficient HTTP streaming."""
#     while True:
#         if camera_id in unresponsive_cameras:
#             break

#         if camera_id in frame_buffers and frame_buffers[camera_id]:
#             frame = frame_buffers[camera_id][-1]
#             yield (b'--frame\r\n'
#                    b'Content-Type: image/jpeg\r\n'
#                    b'Content-Length: ' + f"{len(frame)}".encode() + b'\r\n'
#                    b'\r\n' + frame + b'\r\n')
#         else:
#             break

# def initialize_all_camera_streams():
#     """Starts multiprocessing for all cameras on server startup."""
#     logger.info("Initializing all camera streams on server startup...")
#     for section in Section.objects.all().order_by("id"):
#         for camera in Camera.objects.filter(section=section, is_active=True).order_by("id"):
#             if camera.id not in active_streams:
#                 process = mp.Process(target=stream_camera_ffmpeg, args=(camera.id, camera.get_rtsp_url(), frame_buffers, unresponsive_cameras))
#                 process.start()
#                 active_streams[camera.id] = process

#     logger.info("All camera streams initialized.")

# def video_feed(request, camera_id):
#     """Django view for optimized video streaming."""
#     camera = get_object_or_404(Camera, id=camera_id)
#     if camera_id in unresponsive_cameras:
#         return JsonResponse({"message": "Camera is unresponsive"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

#     if camera_id not in active_streams:
#         process = mp.Process(target=stream_camera_ffmpeg, args=(camera.id, camera.get_rtsp_url(), frame_buffers, unresponsive_cameras))
#         process.start()
#         active_streams[camera.id] = process

#     return StreamingHttpResponse(generate_frames(camera_id), content_type='multipart/x-mixed-replace; boundary=frame')

# class MultiCameraStreamViewSet(viewsets.ViewSet):
#     """Handles multi-camera streaming for sections."""
#     def retrieve(self, request, pk=None):
#         section = get_object_or_404(Section, id=pk)
#         cameras = Camera.objects.filter(section=section, is_active=True)
#         active_stream_urls = {}

#         for camera in cameras:
#             if camera.id not in active_streams:
#                 process = mp.Process(target=stream_camera_ffmpeg, args=(camera.id, camera.get_rtsp_url(), frame_buffers, unresponsive_cameras))
#                 process.start()
#                 active_streams[camera.id] = process
#             active_stream_urls[camera.id] = f"/api/video_feed/{camera.id}/"

#         return JsonResponse({"message": "All camera feeds", "streams": active_stream_urls}, status=status.HTTP_200_OK)

# # Run the initialization function on startup
# startup_process = mp.Process(target=initialize_all_camera_streams)
# startup_process.start()


##########################################################################################################################################################

# # Constants
# MAX_CONCURRENT_STREAMS = 15
# FRAME_TIMEOUT = 20

# # Global State
# active_streams = {}  # {camera_id: process}
# frame_buffers = {}   # {camera_id: deque}
# unresponsive_cameras = set()
# stream_lock = threading.Lock()
# thread_pool_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_STREAMS)
# frame_conditions = {}  # {camera_id: threading.Condition()}

# logger = logging.getLogger(__name__)

# def stream_camera_ffmpeg(camera_id, camera_url):
#     """Starts FFmpeg process for a camera and maintains frame queue."""
#     global active_streams, frame_buffers, unresponsive_cameras

#     logger.debug(f"Starting stream for camera {camera_id} at {camera_url}")

#     with stream_lock:
#         if camera_id in active_streams:
#             logger.debug(f"Camera {camera_id} already streaming.")
#             return  

#         frame_buffers[camera_id] = deque(maxlen=30)
#         frame_conditions[camera_id] = threading.Condition()

#     try:
#         ffmpeg_cmd = [
#             "ffmpeg", "-rtsp_transport", "tcp", "-i", camera_url,
#             "-an", "-vf", "fps=7,scale=640:480", "-f", "image2pipe",
#             "-pix_fmt", "bgr24", "-vcodec", "rawvideo", "-"
#         ]
        
#         process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8)

#         with stream_lock:
#             active_streams[camera_id] = process

#         frame_size = 640 * 480 * 3
#         start_time = time.time()

#         while True:
#             raw_frame = process.stdout.read(frame_size)
#             if len(raw_frame) != frame_size:
#                 if time.time() - start_time > FRAME_TIMEOUT:
#                     logger.error(f"Camera {camera_id} unresponsive. Stream will not restart.")
#                     unresponsive_cameras.add(camera_id)
#                     break
#                 continue
            
#             frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((480, 640, 3))
#             _, jpeg = cv2.imencode(".jpg", frame)

#             with stream_lock:
#                 frame_buffers[camera_id].append(jpeg.tobytes())

#             with frame_conditions[camera_id]:
#                 frame_conditions[camera_id].notify_all()

#             start_time = time.time()

#     except Exception as e:
#         logger.error(f"FFmpeg error for camera {camera_id}: {e}")
#     finally:
#         cleanup_camera_stream(camera_id)


# def cleanup_camera_stream(camera_id):
#     """Cleans up FFmpeg process and frame buffer when a stream stops."""
#     with stream_lock:
#         # Kill the FFmpeg process if it's active and remove it from active_streams
#         if camera_id in active_streams:
#             active_streams[camera_id].kill()
#             del active_streams[camera_id]
        
#         # Remove the frame buffer and condition for the camera
#         if camera_id in frame_buffers:
#             del frame_buffers[camera_id]
        
#         if camera_id in frame_conditions:
#             del frame_conditions[camera_id]

#         logger.debug(f"Cleaned up stream resources for camera {camera_id}")


# def generate_frames(camera_id):
#     """Yields latest frames for efficient HTTP streaming."""
#     while True:
#         with stream_lock:
#             if camera_id not in frame_buffers or camera_id in unresponsive_cameras:
#                 break
        
#         with frame_conditions[camera_id]:
#             frame_conditions[camera_id].wait(timeout=FRAME_TIMEOUT)

#         with stream_lock:
#             if frame_buffers[camera_id]:
#                 frame = frame_buffers[camera_id][-1]
#                 yield (b'--frame\r\n'
#                        b'Content-Type: image/jpeg\r\n'
#                        b'Content-Length: ' + f"{len(frame)}".encode() + b'\r\n'
#                        b'\r\n' + frame + b'\r\n')
#             else:
#                 break


# def initialize_all_camera_streams():
#     """Sequentially starts streaming for all cameras section by section on server startup."""
#     logger.info("Initializing all camera streams on server startup...")

#     sections = Section.objects.all().order_by("id")  # Fetch sections in order
#     for section in sections:
#         cameras = Camera.objects.filter(section=section, is_active=True).order_by("id")
        
#         for camera in cameras:
#             with stream_lock:
#                 if camera.id not in active_streams:
#                     logger.info(f"Starting camera {camera.id} in section {section.id}")
#                     thread_pool_executor.submit(stream_camera_ffmpeg, camera.id, camera.get_rtsp_url())

#         # Introduce a small delay to ensure sequential processing
#         time.sleep(1)  

#     logger.info("All camera streams initialized.")


# def video_feed(request, camera_id):
#     """Django view for optimized video streaming."""
#     camera = get_object_or_404(Camera, id=camera_id)

#     if camera_id in unresponsive_cameras:
#         return JsonResponse({"message": "Camera is unresponsive"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

#     with stream_lock:
#         if camera_id not in active_streams:
#             thread_pool_executor.submit(stream_camera_ffmpeg, camera.id, camera.get_rtsp_url())

#     return StreamingHttpResponse(generate_frames(camera_id), content_type='multipart/x-mixed-replace; boundary=frame')


# class MultiCameraStreamViewSet(viewsets.ViewSet):
#     """Handles multi-camera streaming for sections."""

#     def retrieve(self, request, pk=None):
#         section = get_object_or_404(Section, id=pk)
#         cameras = Camera.objects.filter(section=section, is_active=True)
#         active_stream_urls = {}

#         with stream_lock:
#             for camera in cameras:
#                 if camera.id not in active_streams:
#                     thread_pool_executor.submit(stream_camera_ffmpeg, camera.id, camera.get_rtsp_url())
#                 active_stream_urls[camera.id] = f"/api/video_feed/{camera.id}/"

#         return JsonResponse({"message": "All camera feeds", "streams": active_stream_urls}, status=status.HTTP_200_OK)


# # Run the initialization function on startup
# startup_thread = threading.Thread(target=initialize_all_camera_streams, daemon=True)
# startup_thread.start()

#####################################################################################################################################################33

# # Constants
# MAX_CONCURRENT_STREAMS = 15
# FRAME_TIMEOUT = 20
# RETRY_COUNT = 3
# RECOVERY_CHECK_INTERVAL = 60

# # Global State
# active_streams = {}  # {camera_id: process}
# frame_buffers = {}   # {camera_id: deque}
# unresponsive_cameras = set()
# stream_lock = threading.Lock()
# thread_pool_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_STREAMS)
# frame_conditions = {}  # {camera_id: threading.Condition()}

# logger = logging.getLogger(__name__)

# def stream_camera_ffmpeg(camera_id, camera_url):
#     """Starts FFmpeg process for a camera and maintains frame queue."""
#     global active_streams, frame_buffers, unresponsive_cameras

#     logger.debug(f"Starting stream for camera {camera_id} at {camera_url}")

#     with stream_lock:
#         if camera_id in active_streams:
#             logger.debug(f"Camera {camera_id} already streaming.")
#             return  

#         frame_buffers[camera_id] = deque(maxlen=30)
#         frame_conditions[camera_id] = threading.Condition()

#     try:
#         ffmpeg_cmd = [
#             "ffmpeg", "-rtsp_transport", "tcp", "-i", camera_url,
#             "-an", "-vf", "fps=7,scale=640:480", "-f", "image2pipe",
#             "-pix_fmt", "bgr24", "-vcodec", "rawvideo", "-"
#         ]
        
#         process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8)

#         with stream_lock:
#             active_streams[camera_id] = process

#         frame_size = 640 * 480 * 3
#         start_time = time.time()

#         while True:
#             raw_frame = process.stdout.read(frame_size)
#             if len(raw_frame) != frame_size:
#                 if time.time() - start_time > FRAME_TIMEOUT:
#                     logger.error(f"Camera {camera_id} unresponsive.")
#                     unresponsive_cameras.add(camera_id)
#                     restart_stream(camera_id)
#                     break
#                 continue
            
#             frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((480, 640, 3))
#             _, jpeg = cv2.imencode(".jpg", frame)

#             with stream_lock:
#                 frame_buffers[camera_id].append(jpeg.tobytes())

#             with frame_conditions[camera_id]:
#                 frame_conditions[camera_id].notify_all()

#             start_time = time.time()

#     except Exception as e:
#         logger.error(f"FFmpeg error for camera {camera_id}: {e}")
#     finally:
#         cleanup_camera_stream(camera_id)


# def restart_stream(camera_id):
#     """Retries stream if a camera is unresponsive."""
#     camera = Camera.objects.filter(id=camera_id, is_active=True).first()
#     if not camera:
#         return

#     for attempt in range(1, RETRY_COUNT + 1):
#         logger.info(f"Retrying stream for camera {camera_id}, attempt {attempt}/{RETRY_COUNT}")

#         with stream_lock:
#             if camera_id in active_streams:
#                 active_streams[camera_id].kill()
#                 del active_streams[camera_id]

#         time.sleep(3)

#         try:
#             thread_pool_executor.submit(stream_camera_ffmpeg, camera.id, camera.get_rtsp_url())
#             unresponsive_cameras.discard(camera_id)
#             logger.info(f"Camera {camera_id} restarted successfully.")
#             return
#         except Exception as e:
#             logger.error(f"Failed to restart camera {camera_id}: {e}")

#     logger.error(f"Camera {camera_id} remains unresponsive after {RETRY_COUNT} retries.")


# def cleanup_camera_stream(camera_id):
#     """Cleans up FFmpeg process and frame buffer when a stream stops."""
#     with stream_lock:
#         # Kill the FFmpeg process if it's active and remove it from active_streams
#         if camera_id in active_streams:
#             active_streams[camera_id].kill()
#             del active_streams[camera_id]
        
#         # Remove the frame buffer and condition for the camera
#         if camera_id in frame_buffers:
#             del frame_buffers[camera_id]
        
#         if camera_id in frame_conditions:
#             del frame_conditions[camera_id]

#         logger.debug(f"Cleaned up stream resources for camera {camera_id}")


# def generate_frames(camera_id):
#     """Yields latest frames for efficient HTTP streaming."""
#     while True:
#         with stream_lock:
#             if camera_id not in frame_buffers or camera_id in unresponsive_cameras:
#                 break
        
#         with frame_conditions[camera_id]:
#             frame_conditions[camera_id].wait(timeout=FRAME_TIMEOUT)

#         with stream_lock:
#             if frame_buffers[camera_id]:
#                 frame = frame_buffers[camera_id][-1]
#                 yield (b'--frame\r\n'
#                        b'Content-Type: image/jpeg\r\n'
#                        b'Content-Length: ' + f"{len(frame)}".encode() + b'\r\n'
#                        b'\r\n' + frame + b'\r\n')
#             else:
#                 break


# def initialize_all_camera_streams():
#     """Sequentially starts streaming for all cameras section by section on server startup."""
#     logger.info("Initializing all camera streams on server startup...")

#     sections = Section.objects.all().order_by("id")  # Fetch sections in order
#     for section in sections:
#         cameras = Camera.objects.filter(section=section, is_active=True).order_by("id")
        
#         for camera in cameras:
#             with stream_lock:
#                 if camera.id not in active_streams:
#                     logger.info(f"Starting camera {camera.id} in section {section.id}")
#                     thread_pool_executor.submit(stream_camera_ffmpeg, camera.id, camera.get_rtsp_url())

#         # Introduce a small delay to ensure sequential processing
#         time.sleep(1)  

#     logger.info("All camera streams initialized.")


# def video_feed(request, camera_id):
#     """Django view for optimized video streaming."""
#     camera = get_object_or_404(Camera, id=camera_id)

#     if camera_id in unresponsive_cameras:
#         return JsonResponse({"message": "Camera is unresponsive"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

#     with stream_lock:
#         if camera_id not in active_streams:
#             thread_pool_executor.submit(stream_camera_ffmpeg, camera.id, camera.get_rtsp_url())

#     return StreamingHttpResponse(generate_frames(camera_id), content_type='multipart/x-mixed-replace; boundary=frame')


# class MultiCameraStreamViewSet(viewsets.ViewSet):
#     """Handles multi-camera streaming for sections."""

#     def retrieve(self, request, pk=None):
#         section = get_object_or_404(Section, id=pk)
#         cameras = Camera.objects.filter(section=section, is_active=True)
#         active_stream_urls = {}

#         with stream_lock:
#             for camera in cameras:
#                 if camera.id not in active_streams:
#                     thread_pool_executor.submit(stream_camera_ffmpeg, camera.id, camera.get_rtsp_url())
#                 active_stream_urls[camera.id] = f"/api/video_feed/{camera.id}/"

#         return Response({"message": "All camera feeds", "streams": active_stream_urls}, status=status.HTTP_200_OK)


# # Run the initialization function on startup
# startup_thread = threading.Thread(target=initialize_all_camera_streams, daemon=True)
# startup_thread.start()

######################################################################################################################################################

# # Constants
# MAX_CONCURRENT_STREAMS = 15
# FRAME_TIMEOUT = 20
# RETRY_COUNT = 3
# RECOVERY_CHECK_INTERVAL = 60

# # Global State
# active_streams = {}  # {camera_id: process}
# frame_buffers = {}   # {camera_id: deque}
# unresponsive_cameras = set()
# stream_lock = threading.Lock()
# thread_pool_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_STREAMS)
# frame_conditions = {}  # {camera_id: threading.Condition()}

# logger = logging.getLogger(__name__)

# def stream_camera_ffmpeg(camera_id, camera_url):
#     """Starts FFmpeg process for a camera and maintains frame queue."""
#     global active_streams, frame_buffers, unresponsive_cameras
    
#     logger.debug(f"Starting stream for camera {camera_id} at {camera_url}")

#     with stream_lock:
#         if camera_id in active_streams:
#             logger.debug(f"Camera {camera_id} already streaming.")
#             return  

#         frame_buffers[camera_id] = deque(maxlen=30)
#         frame_conditions[camera_id] = threading.Condition()

#     try:
#         ffmpeg_cmd = [
#             "ffmpeg", "-rtsp_transport", "tcp", "-i", camera_url,
#             "-an", "-vf", "fps=7,scale=640:480", "-f", "image2pipe",
#             "-pix_fmt", "bgr24", "-vcodec", "rawvideo", "-"
#         ]
        
#         process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8)

#         with stream_lock:
#             active_streams[camera_id] = process

#         frame_size = 640 * 480 * 3
#         start_time = time.time()

#         while True:
#             raw_frame = process.stdout.read(frame_size)
#             if len(raw_frame) != frame_size:
#                 if time.time() - start_time > FRAME_TIMEOUT:
#                     logger.error(f"Camera {camera_id} unresponsive.")
#                     unresponsive_cameras.add(camera_id)
#                     restart_stream(camera_id)
#                     break
#                 continue
            
#             frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((480, 640, 3))
#             _, jpeg = cv2.imencode(".jpg", frame)

#             with stream_lock:
#                 frame_buffers[camera_id].append(jpeg.tobytes())

#             with frame_conditions[camera_id]:
#                 frame_conditions[camera_id].notify_all()

#             start_time = time.time()

#     except Exception as e:
#         logger.error(f"FFmpeg error for camera {camera_id}: {e}")
#     finally:
#         cleanup_camera_stream(camera_id)


# def restart_stream(camera_id):
#     """Retries stream if a camera is unresponsive."""
#     camera = Camera.objects.filter(id=camera_id, is_active=True).first()
#     if not camera:
#         return

#     for attempt in range(1, RETRY_COUNT + 1):
#         logger.info(f"Retrying stream for camera {camera_id}, attempt {attempt}/{RETRY_COUNT}")

#         with stream_lock:
#             if camera_id in active_streams:
#                 active_streams[camera_id].kill()
#                 del active_streams[camera_id]

#         time.sleep(3)

#         try:
#             thread_pool_executor.submit(stream_camera_ffmpeg, camera.id, camera.get_rtsp_url())
#             unresponsive_cameras.discard(camera_id)
#             logger.info(f"Camera {camera_id} restarted successfully.")
#             return
#         except Exception as e:
#             logger.error(f"Failed to restart camera {camera_id}: {e}")

#     logger.error(f"Camera {camera_id} remains unresponsive after {RETRY_COUNT} retries.")


# def cleanup_camera_stream(camera_id):
#     """Cleans up FFmpeg process and frame buffer when a stream stops."""
#     with stream_lock:
#         # Kill the FFmpeg process if it's active and remove it from active_streams
#         if camera_id in active_streams:
#             active_streams[camera_id].kill()
#             del active_streams[camera_id]
        
#         # Remove the frame buffer and condition for the camera
#         if camera_id in frame_buffers:
#             del frame_buffers[camera_id]
        
#         if camera_id in frame_conditions:
#             del frame_conditions[camera_id]

#         logger.debug(f"Cleaned up stream resources for camera {camera_id}")


# def generate_frames(camera_id):
#     """Yields latest frames for efficient HTTP streaming."""
#     while True:
#         with stream_lock:
#             if camera_id not in frame_buffers or camera_id in unresponsive_cameras:
#                 break
        
#         with frame_conditions[camera_id]:
#             frame_conditions[camera_id].wait(timeout=FRAME_TIMEOUT)

#         with stream_lock:
#             if frame_buffers[camera_id]:
#                 frame = frame_buffers[camera_id][-1]
#                 yield (b'--frame\r\n'
#                        b'Content-Type: image/jpeg\r\n'
#                        b'Content-Length: ' + f"{len(frame)}".encode() + b'\r\n'
#                        b'\r\n' + frame + b'\r\n')
#             else:
#                 break

# def video_feed(request, camera_id):
#     """Django view for optimized video streaming."""
#     camera = get_object_or_404(Camera, id=camera_id)

#     if camera_id in unresponsive_cameras:
#         return JsonResponse({"message": "Camera is unresponsive"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

#     with stream_lock:
#         if camera_id not in active_streams:
#             thread_pool_executor.submit(stream_camera_ffmpeg, camera.id, camera.get_rtsp_url())

#     return StreamingHttpResponse(generate_frames(camera_id), content_type='multipart/x-mixed-replace; boundary=frame')

# class MultiCameraStreamViewSet(viewsets.ViewSet):
#     """Handles multi-camera streaming for sections."""

#     def retrieve(self, request, pk=None):
#         section = get_object_or_404(Section, id=pk)
#         cameras = Camera.objects.filter(section=section, is_active=True)
#         active_stream_urls = {}

#         with stream_lock:
#             for camera in cameras:
#                 if camera.id not in active_streams:
#                     thread_pool_executor.submit(stream_camera_ffmpeg, camera.id, camera.get_rtsp_url())
#                 active_stream_urls[camera.id] = f"/api/video_feed/{camera.id}/"

#         return Response({"message": "All camera feeds", "streams": active_stream_urls}, status=status.HTTP_200_OK)

########################################################################################################################################################


# # Constants
# MAX_CONCURRENT_STREAMS = 15
# FRAME_TIMEOUT = 20
# RETRY_COUNT = 3
# RECOVERY_CHECK_INTERVAL = 60

# # Global State
# active_streams = {}  # {camera_id: process}
# frame_buffers = {}   # {camera_id: deque}
# unresponsive_cameras = set()
# stream_lock = threading.Lock()
# thread_pool_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_STREAMS)
# frame_conditions = {}  # {camera_id: threading.Condition()}


# def stream_camera_ffmpeg(camera_id, camera_url):
#     """Starts FFmpeg process for a camera and maintains frame queue."""
#     global active_streams, frame_buffers, unresponsive_cameras
    
#     logger.debug(f"Starting stream for camera {camera_id} at {camera_url}")

#     with stream_lock:
#         if camera_id in active_streams:
#             logger.debug(f"Camera {camera_id} already streaming.")
#             return  

#         frame_buffers[camera_id] = deque(maxlen=30)
#         frame_conditions[camera_id] = threading.Condition()

#     try:
#         ffmpeg_cmd = [
#             "ffmpeg", "-rtsp_transport", "tcp", "-i", camera_url,
#             "-an", "-vf", "fps=7,scale=640:480", "-f", "image2pipe",
#             "-pix_fmt", "bgr24", "-vcodec", "rawvideo", "-"
#         ]
        
#         process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8)

#         with stream_lock:
#             active_streams[camera_id] = process

#         frame_size = 640 * 480 * 3
#         start_time = time.time()

#         while True:
#             raw_frame = process.stdout.read(frame_size)
#             if len(raw_frame) != frame_size:
#                 if time.time() - start_time > FRAME_TIMEOUT:
#                     logger.error(f"Camera {camera_id} unresponsive.")
#                     unresponsive_cameras.add(camera_id)
#                     restart_stream(camera_id)
#                     break
#                 continue
            
#             frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((480, 640, 3))
#             _, jpeg = cv2.imencode(".jpg", frame)

#             with stream_lock:
#                 frame_buffers[camera_id].append(jpeg.tobytes())

#             with frame_conditions[camera_id]:
#                 frame_conditions[camera_id].notify_all()

#             start_time = time.time()

#     except Exception as e:
#         logger.error(f"FFmpeg error for camera {camera_id}: {e}")
#     finally:
#         cleanup_camera_stream(camera_id)


# def restart_stream(camera_id):
#     """Retries stream if a camera is unresponsive."""
#     camera = Camera.objects.filter(id=camera_id, is_active=True).first()
#     if not camera:
#         return

#     for attempt in range(1, RETRY_COUNT + 1):
#         logger.info(f"Retrying stream for camera {camera_id}, attempt {attempt}/{RETRY_COUNT}")

#         with stream_lock:
#             if camera_id in active_streams:
#                 active_streams[camera_id].kill()
#                 del active_streams[camera_id]

#         time.sleep(3)

#         try:
#             thread_pool_executor.submit(stream_camera_ffmpeg, camera.id, camera.get_rtsp_url())
#             unresponsive_cameras.discard(camera_id)
#             logger.info(f"Camera {camera_id} restarted successfully.")
#             return
#         except Exception as e:
#             logger.error(f"Failed to restart camera {camera_id}: {e}")

#     logger.error(f"Camera {camera_id} remains unresponsive after {RETRY_COUNT} retries.")


# def cleanup_camera_stream(camera_id):
#     """Cleans up FFmpeg process and frame buffer when a stream stops."""
#     with stream_lock:
#         # Kill the FFmpeg process if it's active and remove it from active_streams
#         if camera_id in active_streams:
#             active_streams[camera_id].kill()
#             del active_streams[camera_id]
        
#         # Remove the frame buffer and condition for the camera
#         if camera_id in frame_buffers:
#             del frame_buffers[camera_id]
        
#         if camera_id in frame_conditions:
#             del frame_conditions[camera_id]

#         logger.debug(f"Cleaned up stream resources for camera {camera_id}")


# def generate_frames(camera_id):
#     """Yields latest frames for efficient HTTP streaming."""
#     while True:
#         with stream_lock:
#             if camera_id not in frame_buffers or camera_id in unresponsive_cameras:
#                 break
        
#         with frame_conditions[camera_id]:
#             frame_conditions[camera_id].wait(timeout=FRAME_TIMEOUT)

#         with stream_lock:
#             if frame_buffers[camera_id]:
#                 frame = frame_buffers[camera_id].pop()
#                 yield (b'--frame\r\n'
#                        b'Content-Type: image/jpeg\r\n'
#                        b'Content-Length: ' + f"{len(frame)}".encode() + b'\r\n'
#                        b'\r\n' + frame + b'\r\n')
#             else:
#                 break


# def video_feed(request, camera_id):
#     """Django view for optimized video streaming."""
#     camera = get_object_or_404(Camera, id=camera_id)

#     if camera_id in unresponsive_cameras:
#         return JsonResponse({"message": "Camera is unresponsive"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

#     with stream_lock:
#         if camera_id not in active_streams:
#             thread_pool_executor.submit(stream_camera_ffmpeg, camera.id, camera.get_rtsp_url())

#     return StreamingHttpResponse(generate_frames(camera_id), content_type='multipart/x-mixed-replace; boundary=frame')


# class MultiCameraStreamViewSet(viewsets.ViewSet):
#     """Handles multi-camera streaming for sections."""

#     def retrieve(self, request, pk=None):
#         section = get_object_or_404(Section, id=pk)
#         cameras = Camera.objects.filter(section=section, is_active=True)
#         active_stream_urls = {}

#         # Parallel execution of camera stream starts
#         futures = {camera.id: thread_pool_executor.submit(self.start_camera, camera) for camera in cameras}

#         for camera_id, future in futures.items():
#             result = future.result()
#             if result:
#                 active_stream_urls.update(result)

#         return Response({"message": "All camera feeds", "streams": active_stream_urls}, status=status.HTTP_200_OK)

#     def start_camera(self, camera):
#         """Starts camera stream if not active."""
#         with stream_lock:
#             if camera.id not in active_streams:
#                 thread_pool_executor.submit(stream_camera_ffmpeg, camera.id, camera.get_rtsp_url())
#         return {camera.id: f"/api/video_feed/{camera.id}/"}

#########################################################################################################################################################

# # Constants
# MAX_CONCURRENT_STREAMS = 15  # Increase the concurrent streams limit
# FRAME_TIMEOUT = 20  # Max time to wait for the first frame in seconds
# RETRY_COUNT = 1  # Number of retry attempts for an unresponsive camera

# # Thread-safe storage for FFmpeg processes and frame queues
# active_streams = {}
# frame_queues = {}
# unresponsive_cameras = set()
# stream_lock = threading.Lock()

# # Set the maximum number of concurrent camera streams
# thread_pool_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_STREAMS)

# # Stream handling and FFmpeg process
# def stream_camera_ffmpeg(camera_id, camera_url):
#     """
#     Starts an FFmpeg process to capture frames from the camera.
#     If the camera is unresponsive, it is marked accordingly.
#     """
#     global active_streams, frame_queues, unresponsive_cameras
#     logger.debug(f"Attempting to start stream for camera {camera_id} at {camera_url}")
    
#     with stream_lock:
#         if camera_id in active_streams:
#             logger.debug(f"Camera {camera_id} is already streaming.")
#             return  # Process already running
        
#         frame_queues[camera_id] = queue.Queue(maxsize=30)
#         logger.debug(f"Queue created for camera {camera_id}")

#     try:
#         ffmpeg_cmd = [
#             "ffmpeg", "-rtsp_transport", "tcp", "-i", camera_url,
#             "-an", "-vf", "fps=7,scale=640:480", "-f", "image2pipe",
#             "-pix_fmt", "bgr24", "-vcodec", "rawvideo", "-"
#         ]
        
#         logger.debug(f"Running FFmpeg command for camera {camera_id}: {' '.join(ffmpeg_cmd)}")
#         process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=10**8)

#         with stream_lock:
#             active_streams[camera_id] = process
#             logger.debug(f"FFmpeg process started for camera {camera_id}")

#         frame_size = 640 * 480 * 3
#         start_time = time.time()

#         while True:
#             raw_frame = process.stdout.read(frame_size)
            
#             if len(raw_frame) != frame_size:
#                 if time.time() - start_time > FRAME_TIMEOUT:
#                     logger.error(f"Camera {camera_id} unresponsive after retry. Marking as unresponsive.")
#                     unresponsive_cameras.add(camera_id)
#                     break
#                 continue
            
#             frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((480, 640, 3))
#             _, jpeg = cv2.imencode(".jpg", frame)
            
#             with stream_lock:
#                 if frame_queues[camera_id].full():
#                     frame_queues[camera_id].get()
#                 frame_queues[camera_id].put(jpeg.tobytes())
            
#             start_time = time.time()  # Reset timeout
#             logger.debug(f"Frame captured and added to queue for camera {camera_id}")

#     except Exception as e:
#         logger.error(f"FFmpeg Stream Error for camera {camera_id}: {e}")
#     finally:
#         with stream_lock:
#             if camera_id in active_streams:
#                 process.kill()  # Terminate the process immediately
#                 del active_streams[camera_id]
#                 del frame_queues[camera_id]
#                 logger.debug(f"FFmpeg process and queue cleaned up for camera {camera_id}")

# def generate_frames(camera_id):
#     """Yields frames from the queue for smooth streaming."""
#     while True:
#         with stream_lock:
#             if camera_id not in frame_queues or camera_id in unresponsive_cameras:
#                 logger.debug(f"Camera {camera_id} is unresponsive or not active.")
#                 break
#         try:
#             frame = frame_queues[camera_id].get(timeout=FRAME_TIMEOUT)
#             if frame is None:
#                 logger.debug(f"No frame to generate for camera {camera_id}.")
#                 break
#             yield (b'--frame\r\n'
#                    b'Content-Type: image/jpeg\r\n'
#                    b'Content-Length: ' + f"{len(frame)}".encode() + b'\r\n'
#                    b'\r\n' + frame + b'\r\n')
#         except queue.Empty:
#             logger.debug(f"Queue empty for camera {camera_id}, no frames to generate.")
#             break

# def video_feed(request, camera_id):
#     """Django view for optimized video streaming."""
#     logger.debug(f"Fetching video feed for camera {camera_id}")
    
#     camera = get_object_or_404(Camera, id=camera_id)
    
#     # If the camera is unresponsive, return API response with status
#     if camera_id in unresponsive_cameras:
#         logger.error(f"Camera {camera_id} is unresponsive, returning error.")
#         return JsonResponse({"message": "Camera is unresponsive", "status": status.HTTP_503_SERVICE_UNAVAILABLE})

#     with stream_lock:
#         if camera_id not in active_streams:
#             logger.debug(f"Starting camera {camera_id} stream.")
#             thread_pool_executor.submit(stream_camera_ffmpeg, camera_id, camera.get_rtsp_url())
    
#     # Return StreamingHttpResponse for the video feed
#     logger.debug(f"Returning video feed for camera {camera_id}")
#     return StreamingHttpResponse(generate_frames(camera_id),
#                                  content_type='multipart/x-mixed-replace; boundary=frame')

# # Ensure that the executor is not shutdown before submitting tasks.
# def create_executor():
#     """Creates a new thread pool executor if necessary."""
#     global thread_pool_executor
#     if thread_pool_executor._shutdown:
#         logger.debug("Creating new ThreadPoolExecutor")
#         thread_pool_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_STREAMS)

# class MultiCameraStreamViewSet(viewsets.ViewSet):
#     """
#     ViewSet to stream multiple cameras for a specific section.
#     """
#     @swagger_auto_schema(
#         operation_summary="Retrieve Active Camera Streams for a Section",
#         operation_description="Fetches and returns active camera streams for the specified section.",
#         responses={ 
#             200: openapi.Response(
#                 description="Returns a list of active camera streams.",
#                 examples={ 
#                     "application/json": { 
#                         "streams": { 
#                             "1": "/api/video_feed/1/", 
#                             "2": "/api/video_feed/2/" 
#                         } 
#                     }
#                 }
#             ),
#             400: openapi.Response(description="Invalid section ID."),
#             404: openapi.Response(description="Section not found."),
#             503: openapi.Response(description="No active cameras found."),
#         }
#     )
#     def retrieve(self, request, pk=None):
#         section = get_object_or_404(Section, id=pk)
#         cameras = Camera.objects.filter(section=section, is_active=True)
#         active_stream_urls = {}
#         unresponsive_camera_urls = {}

#         def process_camera(camera):
#             """Launch camera stream process if not running.""" 
#             try:
#                 logger.debug(f"Processing camera {camera.id} for section {pk}")
#                 create_executor()  # Ensure the thread pool is active

#                 with stream_lock:
#                     if camera.id in unresponsive_cameras:
#                         unresponsive_camera_urls[camera.id] = "unresponsive"
#                         return None  # Skip unresponsive camera
#                     if camera.id not in active_streams:
#                         logger.debug(f"Starting stream for camera {camera.id}")
#                         thread_pool_executor.submit(stream_camera_ffmpeg, camera.id, camera.get_rtsp_url())
#                     return {camera.id: f"/api/video_feed/{camera.id}/"}
#             except Exception as e:
#                 logger.error(f"Error processing camera {camera.id} in section {pk}: {e}")
#                 unresponsive_cameras.add(camera.id)
#                 unresponsive_camera_urls[camera.id] = "unresponsive"
#                 return None

#         # Using ThreadPoolExecutor to manage multiple camera streams
#         futures = [thread_pool_executor.submit(process_camera, camera) for camera in cameras]
#         for future in as_completed(futures):
#             result = future.result()
#             if result:
#                 active_stream_urls.update(result)

#         # Prepare the response
#         if not active_stream_urls and not unresponsive_camera_urls:
#             logger.error(f"No active cameras found in section {pk}.")
#             return Response({"message": "No active cameras found.", "status": status.HTTP_503_SERVICE_UNAVAILABLE})
        
#         response_data = {"message": "All camera feeds", "section_id": pk, "streams": active_stream_urls}

#         if unresponsive_camera_urls:
#             response_data["unresponsive_cameras"] = unresponsive_camera_urls

#         logger.debug(f"Returning active camera streams for section {pk}")
#         return Response(response_data, status=status.HTTP_200_OK)

######################################################################################################################################################

# # Store active FFmpeg processes
# active_streams = {}

# def stream_camera_ffmpeg(camera_url, frame_queue):
#     """FFmpeg-based streaming function optimized for real-time feed."""
#     global active_streams

#     if camera_url in active_streams:
#         process = active_streams[camera_url]

#     else:
#         try:
#             ffmpeg_cmd = [
#                 "ffmpeg",
#                 "-rtsp_transport", "tcp",
#                 "-i", camera_url,
#                 "-an",  # No audio
#                 "-vf", "fps=7,scale=640:480",  # Optimize frame rate & scale for better performance
#                 "-f", "image2pipe",
#                 "-pix_fmt", "bgr24",  
#                 "-vcodec", "rawvideo",
#                 "-"
#             ]

#             process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8)
#             active_streams[camera_url] = process

#             frame_size = 640 * 480 * 3  # Frame size for 640x480, 3 channels (BGR)
#             while True:
#                 raw_frame = process.stdout.read(frame_size)
#                 if len(raw_frame) != frame_size:
#                     continue  # Skip if frame is incomplete
                
#                 frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((480, 640, 3))  # Convert bytes to NumPy array
#                 _, jpeg = cv2.imencode(".jpg", frame)  # Encode frame as JPEG

#                 frame_queue.put(jpeg.tobytes())

#         except Exception as e:
#             logger.error(f"FFmpeg Stream Error: {e}")
        
#         finally:
#             if process:
#                 process.kill()


# def generate_frames(camera_url):
#     """Generator function to yield frames for smooth streaming."""
#     frame_queue = Queue(maxsize=100)  # Prevent memory overload
#     process = Process(target=stream_camera_ffmpeg, args=(camera_url, frame_queue))
#     process.start()

#     try:
#         while True:
#             frame = frame_queue.get()
#             if frame is None:
#                 break  # Stop if no frames

#             yield (b'--frame\r\n'
#                    b'Content-Type: image/jpeg\r\n'
#                    b'Content-Length: ' + f"{len(frame)}".encode() + b'\r\n'
#                    b'\r\n' + frame + b'\r\n')

#     except Exception as e:
#         logger.error(f"Frame Generator Error: {e}")
    
#     finally:
#         process.terminate()


# def video_feed(request, camera_id):
#     """Django view to handle optimized video streaming."""
#     try:
#         camera = Camera.objects.get(id=camera_id)
#         camera_url = camera.get_rtsp_url()

#         return StreamingHttpResponse(generate_frames(camera_url),
#                                      content_type='multipart/x-mixed-replace; boundary=frame')
#     except Camera.DoesNotExist:
#         return JsonResponse({"message": "Camera not found", "status": status.HTTP_404_NOT_FOUND})


    
# class MultiCameraStreamViewSet(viewsets.ViewSet):
#     """
#     ViewSet to stream multiple cameras for a specific section.
#     """
#     @swagger_auto_schema(
#         operation_summary="Retrieve Active Camera Streams for a Section",
#         operation_description="Fetches and returns active camera streams for the specified section.",
#         responses={
#             200: openapi.Response(
#                 description="Returns a list of active camera streams.",
#                 examples={
#                     "application/json": {
#                         "streams": {
#                             "1": "/api/video_feed/1/",
#                             "2": "/api/video_feed/2/"
#                         }
#                     }
#                 }
#             ),
#             400: openapi.Response(description="Invalid section ID."),
#             404: openapi.Response(description="Section not found."),
#             503: openapi.Response(description="No active cameras found."),
#         }
#     )
#     def retrieve(self, request, pk=None):
#         try:
#             section = Section.objects.get(id=pk)
#         except Section.DoesNotExist:
#             return Response({"message": "Section not found.", "status": status.HTTP_404_NOT_FOUND})

#         cameras = Camera.objects.filter(section=section, is_active=True)
#         active_streams = {}

#         def process_camera(camera):
#             """Checks camera status and adds to active streams if reachable."""
#             camera_url = f"/api/video_feed/{camera.id}/"
#             active_streams[camera.id] = camera_url

#         # Use ThreadPoolExecutor for parallel processing
#         with ThreadPoolExecutor(max_workers=min(len(cameras), 30)) as executor:
#             executor.map(process_camera, cameras)

#         if not active_streams:
#             return Response({"message": "No active cameras found.", "status": status.HTTP_503_SERVICE_UNAVAILABLE})

#         return Response({"message": "All cameras feed path", "section_id": pk, "streams": active_streams, "status": status.HTTP_200_OK})

#########################################################################################################################################################

# import cv2
# import time
# import logging
# import threading
# from concurrent.futures import ThreadPoolExecutor
# from django.http import StreamingHttpResponse, JsonResponse
# from django.shortcuts import render
# from rest_framework import viewsets, status
# from rest_framework.response import Response
# from drf_yasg.utils import swagger_auto_schema
# from drf_yasg import openapi
# from .models import Seracs, Section, Camera
# from .serializers import SeracSerializer, SectionSerializer, CameraSerializer

# logger = logging.getLogger(__name__)

# class SeracsViewSet(viewsets.ViewSet):
#     """
#     A ViewSet for managing Serac divisions.
#     """
#     @swagger_auto_schema(
#         operation_summary="List all Seracs",
#         operation_description="Fetches all Seracs. This endpoint returns a list of all Seracs available in the system.",
#         responses={
#             200: openapi.Response(
#                 description="List of all Seracs",
#                 examples={
#                     "application/json": {
#                         "results": [
#                             {
#                                 "id": 1,
#                                 "name": "Serac 1",
#                                 "description": "Description for Serac 1"
#                             },
#                             {
#                                 "id": 2,
#                                 "name": "Serac 2",
#                                 "description": "Description for Serac 2"
#                             }
#                         ],
#                         "status": "200 OK"
#                     }
#                 }
#             )
#         }
#     )
#     def list(self, request):
#         seracs = Seracs.objects.all()
#         serializer = SeracSerializer(seracs, many=True)
#         return Response({"results": serializer.data, "status": status.HTTP_200_OK})


#     @swagger_auto_schema(
#         operation_summary="Retrieve a specific Serac",
#         operation_description="Fetches a specific Serac by its primary key (pk). If the Serac is not found, a 404 Not Found error is returned.",
#         responses={
#             200: openapi.Response(
#                 description="Serac retrieved successfully",
#                 examples={
#                     "application/json": {
#                         "results": {
#                             "id": 1,
#                             "name": "Serac 1",
#                             "description": "Description for Serac 1"
#                         },
#                         "status": "200 OK"
#                     }
#                 }
#             ),
#             404: openapi.Response(
#                 description="Serac not found",
#                 examples={
#                     "application/json": {
#                         "message": "Serac not found",
#                         "status": "404 Not Found"
#                     }
#                 }
#             )
#         }
#     )
#     def retrieve(self, request, pk=None):
#         try:
#             serac = Seracs.objects.get(pk=pk)
#             serializer = SeracSerializer(serac)
#             return Response({"results": serializer.data, "status": status.HTTP_200_OK})
#         except Seracs.DoesNotExist:
#             return Response({"message": "Serac not found", "status": status.HTTP_404_NOT_FOUND})


#     @swagger_auto_schema(
#         operation_summary="Create a new Serac",
#         operation_description="Creates a new Serac using the provided data. The data should be validated according to the SeracSerializer.",
#         request_body=SeracSerializer,
#         responses={
#             201: openapi.Response(
#                 description="Serac created successfully",
#                 examples={
#                     "application/json": {
#                         "message": "Serac created",
#                         "status": "201 Created"
#                     }
#                 }
#             ),
#             400: openapi.Response(
#                 description="Bad Request if the data provided is invalid",
#                 examples={
#                     "application/json": {
#                         "message": "Invalid data",
#                         "errors": {
#                             "name": ["This field is required."],
#                             "description": ["This field is required."]
#                         }
#                     }
#                 }
#             )
#         }
#     )
#     def create(self, request):
#         serializer = SeracSerializer(data=request.data)
#         if serializer.is_valid():
#             serializer.save()
#             return Response({"message": "Serac created", "status": status.HTTP_201_CREATED})
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



# class SectionViewSet(viewsets.ViewSet):
#     """
#     A ViewSet for managing Sections within a Serac.
#     """
#     @swagger_auto_schema(
#         operation_summary="List all sections for a Serac or return an error if `serac_id` is missing",
#         operation_description=(
#             "Fetches all sections for the specified Serac ID. If `serac_id` is not provided, "
#             "it returns a `400 Bad Request` error indicating that the `serac_id` is required."
#         ),
#         manual_parameters=[
#             openapi.Parameter(
#                 name="serac_id", 
#                 in_=openapi.IN_QUERY, 
#                 type=openapi.TYPE_INTEGER, 
#                 description="ID of the Serac to retrieve sections for",
#                 required=True
#             )
#         ],
#         responses={
#             200: openapi.Response(
#                 description="A list of sections",
#                 examples={
#                     "application/json": {
#                         "results": [
#                             {
#                                 "id": 1,
#                                 "name": "Section 1",
#                                 "serac_id": 1
#                             },
#                             {
#                                 "id": 2,
#                                 "name": "Section 2",
#                                 "serac_id": 1
#                             }
#                         ],
#                         "status": "200 OK"
#                     }
#                 }
#             ),
#             400: openapi.Response(
#                 description="Bad Request if `serac_id` is not provided",
#                 examples={
#                     "application/json": {
#                         "message": "serac_id is required"
#                     }
#                 }
#             ),
#             404: openapi.Response(
#                 description="Not Found if Serac does not exist"
#             )
#         }
#     )
#     def list(self, request):
#         serac_id = request.query_params.get('serac_id')

#         if not serac_id:
#             return Response(
#                 {"message": "serac_id is required", "status": status.HTTP_400_BAD_REQUEST}, 
#                 status=status.HTTP_400_BAD_REQUEST
#             )
#         # if serac_id:
#         #     sections = Section.objects.filter(serac_id=serac_id)
#         # else:
#         #     sections = Section.objects.all()
#         # serializer = SectionSerializer(sections, many=True)
#         # return Response({"results": serializer.data, "status": status.HTTP_200_OK})

#         try:
#             serac = Seracs.objects.get(id=serac_id)
#         except Seracs.DoesNotExist:
#             return Response(
#                 {"message": "Serac not found", "status": status.HTTP_404_NOT_FOUND}, 
#                 status=status.HTTP_404_NOT_FOUND
#             )

#         sections = Section.objects.filter(serac_id=serac_id)
#         serializer = SectionSerializer(sections, many=True)
        
#         return Response({"results": serializer.data, "status": status.HTTP_200_OK})

#     @swagger_auto_schema(
#         operation_summary="Retrieve a specific Section",
#         operation_description="Fetches a specific section by its primary key (pk). If the section is not found, a 404 Not Found error will be returned.",
#         responses={
#             200: openapi.Response(
#                 description="Section retrieved successfully",
#                 examples={
#                     "application/json": {
#                         "results": {
#                             "id": 1,
#                             "name": "Section 1",
#                             "serac_id": 1
#                         },
#                         "status": "200 OK"
#                     }
#                 }
#             ),
#             404: openapi.Response(
#                 description="Section not found",
#                 examples={
#                     "application/json": {
#                         "message": "Section not found",
#                         "status": "404 Not Found"
#                     }
#                 }
#             )
#         }
#     )
#     def retrieve(self, request, pk=None):
#         try:
#             section = Section.objects.get(pk=pk)
#             serializer = SectionSerializer(section)
#             return Response({"results": serializer.data, "status": status.HTTP_200_OK})
#         except Section.DoesNotExist:
#             return Response({"message": "Section not found", "status": status.HTTP_404_NOT_FOUND})


#     @swagger_auto_schema(
#         operation_summary="Create a new Section",
#         operation_description=(
#             "Creates a new section using the provided data. The data should match the "
#             "structure defined by the SectionSerializer. If the data is valid, a new section is created."
#         ),
#         request_body=SectionSerializer,
#         responses={
#             201: openapi.Response(
#                 description="Section created successfully",
#                 examples={
#                     "application/json": {
#                         "message": "Section created",
#                         "status": "201 Created"
#                     }
#                 }
#             ),
#             400: openapi.Response(
#                 description="Bad Request if the data provided is invalid",
#                 examples={
#                     "application/json": {
#                         "message": "Invalid data",
#                         "errors": {
#                             "name": ["This field is required."],
#                             "serac_id": ["This field must be a valid integer."]
#                         }
#                     }
#                 }
#             )
#         }
#     )
#     def create(self, request):
#         serializer = SectionSerializer(data=request.data)
#         if serializer.is_valid():
#             serializer.save()
#             return Response({"message": "Section created", "status": status.HTTP_201_CREATED})
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# class CameraViewSet(viewsets.ViewSet):
#     """
#     A ViewSet for managing Cameras within Sections.
#     """
#     @swagger_auto_schema(
#         operation_summary="List all cameras for a given section or all cameras if `section_id` is not provided",
#         operation_description=(
#             "Fetches all cameras for the specified Section ID if `section_id` is provided. "
#             "If no `section_id` is provided, all cameras will be returned."
#         ),
#         manual_parameters=[
#             openapi.Parameter(
#                 name="section_id", 
#                 in_=openapi.IN_QUERY, 
#                 type=openapi.TYPE_INTEGER, 
#                 description="ID of the section to retrieve cameras for",
#                 required=True
#             )
#         ],
#         responses={
#             200: openapi.Response(
#                 description="A list of cameras",
#                 examples={
#                     "application/json": {
#                         "results": [
#                             {
#                                 "id": 1,
#                                 "name": "Camera 1",
#                                 "section_id": 1
#                             },
#                             {
#                                 "id": 2,
#                                 "name": "Camera 2",
#                                 "section_id": 1
#                             }
#                         ],
#                         "status": "200 OK"
#                     }
#                 }
#             ),
#             400: openapi.Response(
#                 description="Bad Request if invalid query parameter",
#                 examples={
#                     "application/json": {
#                         "message": "Invalid section_id"
#                     }
#                 }
#             )
#         }
#     )
#     def list(self, request):
#         section_id = request.query_params.get('section_id')
        
#         if section_id:
#             cameras = Camera.objects.filter(section_id=section_id)
#         else:
#             cameras = Camera.objects.all()

#         serializer = CameraSerializer(cameras, many=True)
#         return Response({"results": serializer.data, "status": status.HTTP_200_OK})

#     @swagger_auto_schema(
#         operation_summary="Retrieve a specific camera",
#         operation_description="Fetches details of a specific camera by its unique ID.",
#         responses={
#             200: openapi.Response(
#                 description="Details of the specified camera",
#                 examples={
#                     "application/json": {
#                         "results": {
#                             "id": 1,
#                             "name": "Camera 1",
#                             "section_id": 1
#                         },
#                         "status": "200 OK"
#                     }
#                 }
#             ),
#             404: openapi.Response(
#                 description="Not Found if the camera with the specified ID does not exist",
#                 examples={
#                     "application/json": {
#                         "message": "Camera not found"
#                     }
#                 }
#             )
#         }
#     )
#     def retrieve(self, request, pk=None):
#         try:
#             camera = Camera.objects.get(pk=pk)
#         except Camera.DoesNotExist:
#             return Response(
#                 {"message": "Camera not found", "status": status.HTTP_404_NOT_FOUND}, 
#                 status=status.HTTP_404_NOT_FOUND
#             )
        
#         serializer = CameraSerializer(camera)
#         return Response({"results": serializer.data, "status": status.HTTP_200_OK})

#     @swagger_auto_schema(
#         operation_summary="Create a new camera",
#         operation_description=(
#             "Creates a new camera entry using the provided data. "
#             "The data should be in the format expected by the CameraSerializer. "
#             "If the data is valid, a new camera is created and a success message is returned."
#         ),
#         request_body=CameraSerializer,
#         responses={
#             201: openapi.Response(
#                 description="Camera created successfully",
#                 examples={
#                     "application/json": {
#                         "message": "Camera created",
#                         "status": "201 Created"
#                     }
#                 }
#             ),
#             400: openapi.Response(
#                 description="Bad Request if the data provided is invalid",
#                 examples={
#                     "application/json": {
#                         "message": "Invalid data",
#                         "errors": {
#                             "name": ["This field is required."],
#                             "section_id": ["This field must be a valid integer."]
#                         }
#                     }
#                 }
#             )
#         }
#     )
#     def create(self, request):
#         serializer = CameraSerializer(data=request.data)
#         if serializer.is_valid():
#             serializer.save()
#             return Response({"message": "Camera created", "status": status.HTTP_201_CREATED})
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



# def check_camera_status(camera_url):
#     """Checks if a camera is reachable quickly using a short timeout."""
#     cap = cv2.VideoCapture(camera_url)
#     is_opened = cap.isOpened()
#     cap.release()
#     return is_opened

# def stream_camera_feed(camera_url):
#     """Yields frames from a camera in a more optimized way."""
#     cap = cv2.VideoCapture(camera_url)
#     cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffering to minimize latency
#     retry_count, max_retries = 0, 3

#     while retry_count < max_retries and not cap.isOpened():
#         logger.warning(f"Camera {camera_url} is down. Retrying... ({retry_count+1}/{max_retries})")
#         time.sleep(2)
#         cap = cv2.VideoCapture(camera_url)
#         retry_count += 1

#     if not cap.isOpened():
#         logger.error(f"Camera {camera_url} is unreachable.")
#         return None

#     try:
#         while True:
#             ret, frame = cap.read()
#             if not ret:
#                 logger.warning(f"Lost connection to {camera_url}. Stopping stream.")
#                 break

#             _, buffer = cv2.imencode('.jpg', frame)
#             yield (b'--frame\r\n'
#                    b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
#     except Exception as e:
#         logger.error(f"Error streaming {camera_url}: {str(e)}")
#     finally:
#         cap.release()

# def video_feed(request, camera_id):
#     """Handles video streaming for a single camera."""
#     try:
#         camera = Camera.objects.get(id=camera_id)
#         camera_url = camera.get_rtsp_url()

#         if check_camera_status(camera_url):
#             return StreamingHttpResponse(stream_camera_feed(camera_url),
#                                          content_type='multipart/x-mixed-replace; boundary=frame')
#         else:
#             return Response({"message": f"Camera {camera_id} is unreachable.", "status": status.HTTP_503_SERVICE_UNAVAILABLE})
#     except Camera.DoesNotExist:
#         return Response({"message": "Camera not found", "status": status.HTTP_404_NOT_FOUND})    
    
# class MultiCameraStreamViewSet(viewsets.ViewSet):
#     """
#     ViewSet to stream multiple cameras for a specific section.
#     """
#     @swagger_auto_schema(
#         operation_summary="Retrieve Active Camera Streams for a Section",
#         operation_description="Fetches and returns active camera streams for the specified section.",
#         responses={
#             200: openapi.Response(
#                 description="Returns a list of active camera streams.",
#                 examples={
#                     "application/json": {
#                         "streams": {
#                             "1": "/api/video_feed/1/",
#                             "2": "/api/video_feed/2/"
#                         }
#                     }
#                 }
#             ),
#             400: openapi.Response(description="Invalid section ID."),
#             404: openapi.Response(description="Section not found."),
#             503: openapi.Response(description="No active cameras found."),
#         }
#     )
#     def retrieve(self, request, pk=None):
#         try:
#             section = Section.objects.get(id=pk)
#         except Section.DoesNotExist:
#             return Response({"message": "Section not found.", "status": status.HTTP_404_NOT_FOUND})

#         cameras = Camera.objects.filter(section=section, is_active=True)
#         active_streams = {}

#         def process_camera(camera):
#             """Checks camera status in parallel."""
#             camera_url = f"/api/video_feed/{camera.id}/"
#             if check_camera_status(camera.get_rtsp_url()):
#                 active_streams[camera.id] = camera_url
#             else:
#                 logger.error(f"Camera {camera.id} at {camera.get_rtsp_url()} is unreachable.")

#         # **Use Multi-threading to speed up processing**
#         with ThreadPoolExecutor(max_workers=min(len(cameras), 10)) as executor:
#             executor.map(process_camera, cameras)

#         if not active_streams:
#             return Response({"message": "No active cameras found.", "status": status.HTTP_503_SERVICE_UNAVAILABLE})

#         return Response({"message": "All cameras feed path", "section_id": pk, "streams": active_streams, "status": status.HTTP_200_OK})

############################################################################################################################################################