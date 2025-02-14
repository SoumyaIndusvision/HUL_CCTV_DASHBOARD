from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserAPIView, LoginAPIView, PasswordResetAPIView

# Create a router and register UserAPIView
router = DefaultRouter()
router.register(r'users', UserAPIView, basename='user')

urlpatterns = [
    path('', include(router.urls)),  # Include the router URLs
    path('login/', LoginAPIView.as_view(), name='user-login'),
    path('password-reset/', PasswordResetAPIView.as_view(), name='password-reset'),
]
