import cv2
import time
import logging
import threading
import numpy as np
import subprocess
import queue
from collections import deque
from multiprocessing import Process, Manager
from concurrent.futures import ThreadPoolExecutor
from django.http import StreamingHttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Seracs, Section, Camera
from .serializers import SeracSerializer, SectionSerializer, CameraSerializer

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
        operation_summary="List all sections for a Serac or return an error if `serac_id` is missing",
        operation_description=(
            "Fetches all sections for the specified Serac ID. If `serac_id` is not provided, "
            "it returns a `400 Bad Request` error indicating that the `serac_id` is required."
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
                description="A list of sections",
                examples={
                    "application/json": {
                        "results": [
                            {
                                "id": 1,
                                "name": "Section 1",
                                "serac_id": 1
                            },
                            {
                                "id": 2,
                                "name": "Section 2",
                                "serac_id": 1
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
        # if serac_id:
        #     sections = Section.objects.filter(serac_id=serac_id)
        # else:
        #     sections = Section.objects.all()
        # serializer = SectionSerializer(sections, many=True)
        # return Response({"results": serializer.data, "status": status.HTTP_200_OK})

        try:
            serac = Seracs.objects.get(id=serac_id)
        except Seracs.DoesNotExist:
            return Response(
                {"message": "Serac not found", "status": status.HTTP_404_NOT_FOUND}, 
                status=status.HTTP_404_NOT_FOUND
            )

        sections = Section.objects.filter(serac_id=serac_id)
        serializer = SectionSerializer(sections, many=True)
        
        return Response({"results": serializer.data, "status": status.HTTP_200_OK})

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
    
# Store running FFmpeg processes & queues
stream_manager = Manager()
active_streams = stream_manager.dict()  # Shared dictionary for FFmpeg processes
frame_queues = stream_manager.dict()  # Shared dictionary for frame queues
MAX_CONCURRENT_STREAMS = 10  # Adjust based on system resources


def stream_camera_ffmpeg(camera_id, camera_url):
    """
    FFmpeg streaming function optimized for real-time feed.
    Ensures a single process per camera and reuses it when needed.
    """
    global active_streams, frame_queues

    if camera_id in active_streams:
        return  # Process already running

    frame_queue = queue.Queue(maxsize=30)  # Prevent memory overload
    frame_queues[camera_id] = frame_queue

    try:
        ffmpeg_cmd = [
            "ffmpeg",
            "-rtsp_transport", "tcp",
            "-i", camera_url,
            "-an",  # No audio
            "-vf", "fps=7,scale=640:480",  # Optimize frame rate & scale
            "-f", "image2pipe",
            "-pix_fmt", "bgr24",
            "-vcodec", "rawvideo",
            "-"
        ]

        process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8)
        active_streams[camera_id] = process

        frame_size = 640 * 480 * 3  # Frame size for 640x480, 3 channels (BGR)

        while True:
            raw_frame = process.stdout.read(frame_size)
            if len(raw_frame) != frame_size:
                continue  # Skip incomplete frame

            frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((480, 640, 3))  # Convert bytes to NumPy array
            _, jpeg = cv2.imencode(".jpg", frame)  # Encode frame as JPEG

            if frame_queue.full():
                frame_queue.get()  # Drop old frame if full
            frame_queue.put(jpeg.tobytes())

    except Exception as e:
        logger.error(f"FFmpeg Stream Error: {e}")
    finally:
        process.kill()
        del active_streams[camera_id]


def generate_frames(camera_id):
    """Generator function to yield frames for smooth streaming."""
    if camera_id not in frame_queues:
        return

    frame_queue = frame_queues[camera_id]

    while True:
        try:
            frame = frame_queue.get(timeout=5)  # Wait max 5s
            if frame is None:
                break  # Stop if no frames

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n'
                   b'Content-Length: ' + f"{len(frame)}".encode() + b'\r\n'
                   b'\r\n' + frame + b'\r\n')

        except queue.Empty:
            break  # Stop if no frames available


def video_feed(request, camera_id):
    """Django view to handle optimized video streaming."""
    camera = get_object_or_404(Camera, id=camera_id)
    camera_url = camera.get_rtsp_url()

    if camera_id not in active_streams:
        threading.Thread(target=stream_camera_ffmpeg, args=(camera_id, camera_url)).start()

    return StreamingHttpResponse(generate_frames(camera_id),
                                 content_type='multipart/x-mixed-replace; boundary=frame')


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
        section = get_object_or_404(Section, id=pk)
        cameras = Camera.objects.filter(section=section, is_active=True)

        # Limit concurrent FFmpeg processes to avoid system overload
        active_streams_count = len(active_streams)
        if active_streams_count >= MAX_CONCURRENT_STREAMS:
            return Response({"message": "Too many streams. Try again later.", "status": status.HTTP_503_SERVICE_UNAVAILABLE})

        active_stream_urls = {}

        def process_camera(camera):
            """Launch camera stream process if not running."""
            if camera.id not in active_streams:
                threading.Thread(target=stream_camera_ffmpeg, args=(camera.id, camera.get_rtsp_url())).start()
            active_stream_urls[camera.id] = f"/api/video_feed/{camera.id}/"

        # Use ThreadPoolExecutor to launch multiple cameras efficiently
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_STREAMS) as executor:
            executor.map(process_camera, cameras)

        if not active_stream_urls:
            return Response({"message": "No active cameras found.", "status": status.HTTP_503_SERVICE_UNAVAILABLE})

        return Response({"message": "All cameras feed path", "section_id": pk, "streams": active_stream_urls, "status": status.HTTP_200_OK})

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

