import os
import time
import signal
import subprocess
import redis
from django.core.cache import cache
from celery import shared_task
from .models import Camera

# Redis Configuration
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)
FRAME_CACHE_KEY = "camera_frame_{camera_id}"
PROCESS_CACHE_KEY = "camera_process_{camera_id}"
UDP_PORT = 12345  # Change this port if needed

@shared_task(bind=True)
def start_camera_stream(self, camera_id):
    """Starts a GPU-accelerated camera stream and streams to Redis via UDP."""
    camera = Camera.objects.filter(id=camera_id).first()
    if not camera:
        return f"Camera {camera_id} not found."

    camera_url = camera.get_rtsp_url()

    # Optimized FFmpeg command for GPU acceleration
    ffmpeg_cmd = [
        "ffmpeg", "-hwaccel", "cuda", "-hwaccel_output_format", "cuda",
        "-c:v", "h264_cuvid",  # Decode with Nvidia GPU
        "-rtsp_transport", "tcp", "-i", camera_url,
        "-vf", "fps=15,scale_npp=640:480",  # Ensure proper frame rate and scaling
        "-c:v", "h264_nvenc", "-preset", "p4", "-gpu", "0",
        "-b:v", "2M", "-bufsize", "4M",
        "-f", "mpegts", f"udp://localhost:{UDP_PORT}"
    ]

    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Store process ID in Redis
    cache.set(PROCESS_CACHE_KEY.format(camera_id=camera_id), process.pid)

    try:
        process.wait()  # Keep process running
    except Exception as e:
        print(f"Camera {camera_id} failed: {e}")
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
