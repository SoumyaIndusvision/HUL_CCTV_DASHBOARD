from django.urls import path
from . import views

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SeracsViewSet, SectionViewSet, CameraViewSet, MultiCameraStreamViewSet, camera_streams, video_feed

router = DefaultRouter()
router.register(r'seracs', SeracsViewSet, basename='serac')
router.register(r'sections', SectionViewSet, basename='section')
router.register(r'cameras', CameraViewSet, basename='camera')
router.register(r'multi_stream', MultiCameraStreamViewSet, basename='multi-stream')


urlpatterns = router.urls + [
    path('video_feed/<int:camera_id>/', views.video_feed, name='video_feed'),
    path('camera_streams/', views.camera_streams, name='camera_streams'),
    
    # path('multi_stream/', views.multi_camera_stream, name='multi_camera_stream'),
]
