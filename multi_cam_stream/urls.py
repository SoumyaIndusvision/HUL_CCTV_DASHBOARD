from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import SeracsViewSet, SectionViewSet, CameraViewSet, MultiCameraStreamViewSet
from . import views

router = DefaultRouter()
router.register(r'seracs', SeracsViewSet, basename='serac')
router.register(r'sections', SectionViewSet, basename='section')
router.register(r'cameras', CameraViewSet, basename='camera')
router.register(r'multi_stream', MultiCameraStreamViewSet, basename='multi-stream')


urlpatterns = router.urls + [
    path('video_feed/<int:camera_id>/', views.video_feed, name='video_feed'),
]
