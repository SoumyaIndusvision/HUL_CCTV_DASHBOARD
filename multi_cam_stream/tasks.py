import os
import subprocess
from django.core.mail import send_mail
from celery import shared_task
from .models import Camera  # Import the Camera model

# Load environment variables from .env file
EMAIL_HOST_USER = os.getenv('EMAIL_USER')
TO_EMAIL = os.getenv('TO_EMAIL')

@shared_task
def ping_cameras_and_send_report():
    active_cameras = []
    inactive_cameras = []

    # Fetch the camera IPs from the database (Camera model)
    camera_ips = Camera.objects.filter(is_active=True).values_list('ip_address', flat=True)

    # Ping each camera IP
    for ip in camera_ips:
        try:
            # Pinging the camera with 1 packet only (-c 1 for Linux)
            result = subprocess.run(["ping", "-c", "1", str(ip)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                active_cameras.append(ip)
            else:
                inactive_cameras.append(ip)
        except Exception as e:
            inactive_cameras.append(ip)  # Assume inactive if any error occurs

    # Compose the email content
    subject = "Camera Status Report"
    message = (
        f"🟢 Active Cameras ({len(active_cameras)}):\n" +
        "\n".join(active_cameras) +
        "\n\n" +
        f"🔴 Inactive Cameras ({len(inactive_cameras)}):\n" +
        "\n".join(inactive_cameras)
    )

    # Send email using Django's email system
    send_mail(
        subject=subject,
        message=message,
        from_email=EMAIL_HOST_USER,
        recipient_list=[TO_EMAIL],
        fail_silently=False,
    )
