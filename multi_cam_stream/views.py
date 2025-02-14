import cv2
import time
import logging
from django.http import StreamingHttpResponse, JsonResponse
from django.shortcuts import render
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
                description="ID of the Serac to retrieve sections for"
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
                description="ID of the section to retrieve cameras for"
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



def check_camera_status(camera_url):
    """Checks if a camera is reachable."""
    cap = cv2.VideoCapture(camera_url)
    status = cap.isOpened()
    cap.release()
    return status

def stream_camera_feed(camera_url):
    """Yields frames from a camera."""
    cap = cv2.VideoCapture(camera_url)
    # cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"H264"))
    # cap.set(cv2.CAP_PROP_RTSP_TRANSPORT, 1) # 1 = TCP

    retry_count = 0
    max_retries = 3

    while retry_count < max_retries and not cap.isOpened():
        logger.warning(f"Camera {camera_url} is down. Retrying... ({retry_count+1}/{max_retries})")
        time.sleep(2)
        cap = cv2.VideoCapture(camera_url)
        retry_count += 1

    if not cap.isOpened():
        logger.error(f"Camera {camera_url} is unreachable. Skipping stream.")
        return None

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.warning(f"Lost connection to {camera_url}. Stopping stream.")
                break

            _, buffer = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    except Exception as e:
        logger.error(f"Error streaming {camera_url}: {str(e)}")
    finally:
        cap.release()

def video_feed(request, camera_id):
    """Handles video streaming."""
    camera = Camera.objects.get(id=camera_id)
    camera_url = camera.get_rtsp_url()

    if check_camera_status(camera_url):
        return StreamingHttpResponse(stream_camera_feed(camera_url),
                                     content_type='multipart/x-mixed-replace; boundary=frame')
    
    else:
        return Response({"message": f"Camera {camera_id} is unreachable.", "status": status.HTTP_503_SERVICE_UNAVAILABLE}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    
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
        """
        Streams multiple active cameras for the given section.
        """

        try:
            section = Section.objects.get(id=pk)
        except Section.DoesNotExist:
            return Response({"message": "Section not found.", "status": status.HTTP_404_NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)
        
        cameras = Camera.objects.filter(section=section, is_active=True)
        active_streams = {}

        for camera in cameras:
            camera_url = f"/api/video_feed/{camera.id}/"  # Generate HTTP URL for streaming
            if check_camera_status(camera.get_rtsp_url()):  # Check if RTSP URL is working
                active_streams[camera.id] = camera_url
            else:
                logger.error(f"Camera {camera.id} at {camera.get_rtsp_url()} is unreachable.")

        if not active_streams:
            return Response({"message": "No active cameras found.", "status": status.HTTP_503_SERVICE_UNAVAILABLE}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response({"message": "All cameras feed path", "section_id": pk, "streams": active_streams, "status": status.HTTP_200_OK}, status=status.HTTP_200_OK)


def camera_streams(request):
    return render(request, 'cameras/camera_stream.html')