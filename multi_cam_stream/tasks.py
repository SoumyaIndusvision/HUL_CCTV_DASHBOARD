import os
import time
import signal
import subprocess
from django.core.cache import cache
from celery import shared_task
from .models import Camera

# Redis keys
PROCESS_CACHE_KEY = "camera_process_{camera_id}"
UDP_PORT = 12345  # Change this port if needed

@shared_task(bind=True)
def start_camera_stream(self, camera_id):
    """Starts a GPU-accelerated camera stream and streams to Redis via UDP."""
    camera = Camera.objects.filter(id=camera_id).first()
    if not camera:
        return f"Camera {camera_id} not found."

    camera_url = camera.get_rtsp_url()

    # FFmpeg command for GPU-accelerated processing
    ffmpeg_cmd = [
        "ffmpeg", "-hwaccel", "cuda", "-c:v", "h264_cuvid",
        "-rtsp_transport", "tcp", "-i", camera_url,
        "-vf", "fps=5,scale_cuda=640:480",
        "-c:v", "h264_nvenc", "-preset", "fast", "-gpu", "0",
        "-f", "mpegts", f"udp://localhost:{UDP_PORT}"
    ]

    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    # Store process ID in Redis
    cache.set(PROCESS_CACHE_KEY.format(camera_id=camera_id), process.pid)

    try:
        process.wait()  # Keep process running
    except Exception:
        restart_camera_stream.delay(camera_id)
    finally:
        cleanup_camera_stream(camera_id)

@shared_task(bind=True)
def restart_camera_stream(self, camera_id):
    """Restarts the camera stream if it fails."""
    cleanup_camera_stream(camera_id)
    time.sleep(2)
    start_camera_stream.delay(camera_id)

@shared_task(bind=True)
def cleanup_camera_stream(self, camera_id):
    """Stops a running camera stream and clears Redis cache."""
    process_pid = cache.get(PROCESS_CACHE_KEY.format(camera_id=camera_id))
    if process_pid:
        try:
            os.kill(process_pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

        cache.delete(PROCESS_CACHE_KEY.format(camera_id=camera_id))
