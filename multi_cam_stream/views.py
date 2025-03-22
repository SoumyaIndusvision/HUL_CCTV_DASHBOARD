import os
import cv2
import time
import signal
import logging
import asyncio
import aiohttp
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
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Lock

logger = logging.getLogger(__name__)

# -----------------------------------------
# Constants
# -----------------------------------------
FRAME_TIMEOUT = 60  # Camera timeout in seconds
PING_TIMEOUT = 1  # 1-second timeout for ping
MAX_CONCURRENT_STREAMS = 30

# -----------------------------------------
# Global Shared State (Using Manager)
# -----------------------------------------
manager = mp.Manager()
frame_buffers = manager.dict()  # {camera_id: Manager().list()}
active_streams = manager.dict()  # {camera_id: process_pid}
current_section = manager.Value("i", -1)  # Track active section ID
section_lock = Lock()

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
            serac = get_object_or_404(Seracs, pk=pk)
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
            serac = get_object_or_404(Seracs, id=serac_id)
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
            section = get_object_or_404(Section, pk=pk)
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
            camera = get_object_or_404(Camera, pk=pk)
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


# ==============================
#  Camera Health Check Functions
# ==============================

async def ping_camera(ip):
    """Asynchronously pings a camera IP to check if it's reachable."""
    process = await asyncio.create_subprocess_shell(
        f"ping -c 1 -W {PING_TIMEOUT} {ip}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await process.communicate()
    return process.returncode == 0  # Return True if ping succeeds


async def check_camera_status(camera):
    """Check if the camera is active using ping and RTSP connection test."""
    if not await ping_camera(camera.ip_address):
        return camera.id, False  # Camera is unreachable via ping


async def check_section_cameras(section_id):
    """Check all cameras in a section concurrently."""
    section = get_object_or_404(Section, id=section_id)
    cameras = Camera.objects.filter(section=section)

    tasks = [check_camera_status(camera) for camera in cameras]
    results = await asyncio.gather(*tasks)

    active_cameras = {camera_id for camera_id, is_active in results if is_active}
    inactive_cameras = {camera_id for camera_id, is_active in results if not is_active}

    return active_cameras, inactive_cameras

# -----------------------------------------
# FUNCTION: Start Camera Stream
# -----------------------------------------
def start_camera_process(camera_id, camera_url):
    """Starts a new camera stream process if not already running."""
    if camera_id in active_streams:
        return  # Process already running
    
    try:
        process = mp.Process(target=stream_camera_ffmpeg, args=(camera_id, camera_url, frame_buffers))
        process.daemon = False
        process.start()
        active_streams[camera_id] = process.pid
        logger.info(f"Started streaming process {process.pid} for camera {camera_id}")
    except Exception as e:
        logger.error(f"Failed to start camera {camera_id}: {e}")

# -----------------------------------------
# FUNCTION: Stream Camera using FFmpeg
# -----------------------------------------
def stream_camera_ffmpeg(camera_id, camera_url, frame_buffers):
    """Handles streaming a camera using FFmpeg."""
    logger.info(f"Starting stream for camera {camera_id} at {camera_url}")

    if camera_id not in frame_buffers:
        frame_buffers[camera_id] = manager.list()
    
    try:
        ffmpeg_cmd = [
            "ffmpeg", "-rtsp_transport", "tcp", "-i", camera_url,
            "-an", "-vf", "fps=5,scale=640:480", "-f", "image2pipe",
            "-pix_fmt", "bgr24", "-vcodec", "rawvideo", "-"
        ]
        process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8)
        active_streams[camera_id] = process.pid
        frame_size = 640 * 480 * 3
        last_frame_time = time.time()

        while True:
            raw_frame = process.stdout.read(frame_size)
            if len(raw_frame) != frame_size:
                if time.time() - last_frame_time > FRAME_TIMEOUT:
                    logger.warning(f"Camera {camera_id} unresponsive. Stopping...")
                    cleanup_camera_stream(camera_id)
                    break  # Ensure the loop exits
                continue

            frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((480, 640, 3))
            _, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])

            if len(frame_buffers[camera_id]) >= 60:
                frame_buffers[camera_id].pop(0)
            
            frame_buffers[camera_id].append(jpeg.tobytes())
            last_frame_time = time.time()

    except Exception as e:
        logger.error(f"Error in stream for camera {camera_id}: {e}")
    finally:
        cleanup_camera_stream(camera_id)
        return 

# -----------------------------------------
# FUNCTION: Cleanup Camera Process
# -----------------------------------------
def cleanup_camera_stream(camera_id):
    """Stops the camera process and removes buffers safely."""
    if camera_id in active_streams:
        pid = active_streams.pop(camera_id, None)  # Retrieve PID instead of Process object

        if pid:
            try:
                os.kill(pid, signal.SIGTERM)  # Attempt graceful termination
                logger.info(f"Sent SIGTERM to process {pid} for camera {camera_id}")

                # Optional: Check if process is still running before force killing
                os.waitpid(pid, os.WNOHANG)  # Non-blocking wait
                logger.info(f"Process {pid} for camera {camera_id} terminated successfully.")

            except OSError as e:
                if "No such process" in str(e):
                    logger.warning(f"Process {pid} for camera {camera_id} already stopped.")
                else:
                    logger.error(f"Error while terminating process {pid} for camera {camera_id}: {e}")

    frame_buffers.pop(camera_id, None)
    logger.info(f"Camera {camera_id} process cleaned up.")

# -----------------------------------------
# DJANGO VIEW: Serve Video Feed
# -----------------------------------------
def video_feed(request, camera_id):
    """Django view for optimized video streaming."""
    camera = get_object_or_404(Camera, id=camera_id)
    if camera_id not in active_streams:
        start_camera_process(camera.id, camera.get_rtsp_url())
    return StreamingHttpResponse(generate_frames(camera_id), content_type='multipart/x-mixed-replace; boundary=frame')

# -----------------------------------------
# FUNCTION: Generate Video Feed Frames
# -----------------------------------------
def generate_frames(camera_id):
    """Yields latest frames for HTTP streaming."""
    while True:
        if camera_id in frame_buffers and frame_buffers[camera_id]:
            try:
                frame = frame_buffers[camera_id][-1]
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n'
                       b'Content-Length: ' + f"{len(frame)}".encode() + b'\r\n'
                       b'\r\n' + frame + b'\r\n')
            except IndexError:
                yield get_blank_frame()
            except KeyError:
                logger.error(f"Frame buffer missing for camera {camera_id}. Retrying...")
        else:
            time.sleep(0.5)

# -----------------------------------------
# FUNCTION: Blank Frame
# -----------------------------------------
def get_blank_frame():
    blank_image = np.zeros((480, 640, 3), dtype=np.uint8)
    _, jpeg = cv2.imencode(".jpg", blank_image, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    return jpeg.tobytes()

# -----------------------------------------
# API VIEW: Multi-Camera Streaming
# -----------------------------------------
class MultiCameraStreamViewSet(viewsets.ViewSet):
    """
    ViewSet to stream multiple cameras for a specific section.
    """
    @swagger_auto_schema(
        operation_summary="Retrieve Active Camera Streams for a Section",
        operation_description="Fetches and returns active camera streams for the specified section.",
        responses={
            200: openapi.Response(
                description="Returns a list of active camera streams.",
                examples={
                    "application/json": {
                        "streams": {
                            "1": "/api/video_feed/1/",
                            "2": "/api/video_feed/2/"
                        }
                    }
                }
            ),
            400: openapi.Response(description="Invalid section ID."),
            404: openapi.Response(description="Section not found."),
            503: openapi.Response(description="No active cameras found."),
        }
    )

    def retrieve(self, request, pk=None):
        """Switches the active section and manages camera streams accordingly."""
        section = get_object_or_404(Section, id=pk)
        cameras = Camera.objects.filter(section=section, is_active=True)
        active_stream_urls = {}

        with section_lock:
            if current_section.value != pk:
                logger.info(f"Switching from section {current_section.value} to section {pk}. Stopping outdated cameras.")

                # Get all cameras in the new section
                new_section_cameras = set(cameras.values_list("id", flat=True))
                current_active_cameras = set(active_streams.keys())

                # Determine which cameras should be stopped (those not in the new section)
                cameras_to_stop = current_active_cameras - new_section_cameras

                # Stop only the cameras that are no longer needed
                with ThreadPoolExecutor(max_workers=5) as executor:
                    executor.map(cleanup_camera_stream, cameras_to_stop)

                # Update current active section
                current_section.value = pk

        # Start new section cameras
        for camera in cameras:
            if camera.id not in active_streams:
                start_camera_process(camera.id, camera.get_rtsp_url())

            active_stream_urls[camera.id] = f"/api/video_feed/{camera.id}/"

        return JsonResponse(
            {"message": "Camera feeds updated", "streams": active_stream_urls},
            status=status.HTTP_200_OK,
        )


################################################### End Code ###################################################