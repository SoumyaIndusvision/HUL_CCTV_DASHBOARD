from django.contrib import admin
from django.urls import path, include, re_path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
# from rest_framework_simplejwt.views import TokenRefreshView
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as static_serve
from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from drf_yasg import openapi

# Define the schema view for Swagger
schema_view = get_schema_view(
    openapi.Info(
        title="Camera Stream API",
        default_version='v1',
        description="API documentation for camera streaming and management",
        terms_of_service="https://www.yourapp.com/terms/",
        contact=openapi.Contact(email="contact@yourapp.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],  # Allow public access to Swagger UI
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('multi_cam_stream.urls')),
    path('api/', include('users.urls')),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]


# if settings.DEBUG:
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
#     urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Final catch-all pattern to serve index.html for single-page applications
# urlpatterns += [re_path(r'^.*$', static_serve, {'path': 'index.html'})]