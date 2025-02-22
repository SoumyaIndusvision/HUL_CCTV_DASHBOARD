import os
import cv2
import time
import signal
import subprocess
import numpy as np
from .models import Camera
from django.core.cache import cache
from django.conf import settings
from celery import shared_task



FRAME_TIMEOUT = 60  # Camera timeout in seconds

# Redis Cache Keys
FRAME_CACHE_KEY = "camera_frame_{camera_id}"
PROCESS_CACHE_KEY = "camera_process_{camera_id}"

# -----------------------------------------
# Celery Task: Start Camera Streaming
# -----------------------------------------
@shared_task(bind=True)
def start_camera_stream(self, camera_id):
    """Starts a camera stream via FFmpeg and stores frames in Redis."""
    camera = Camera.objects.filter(id=camera_id).first()
    if not camera:
        return f"Camera {camera_id} not found."

    camera_url = camera.get_rtsp_url()

    ffmpeg_cmd = [
        "ffmpeg", "-rtsp_transport", "tcp", "2048k", "-i", camera_url,
        "-an", "-vf", "fps=3,scale=480:360,format=yuv420p",
        "-pix_fmt", "yuv420p", "-vcodec", "h264_nvenc", "-f", "image2pipe", "-"
    ]
    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8)

    # Store process ID in Redis
    cache.set(PROCESS_CACHE_KEY.format(camera_id=camera_id), process.pid)

    frame_size = 480 * 360 * 3
    last_frame_time = time.time()

    try:
        while True:
            raw_frame = process.stdout.read(frame_size)
            if len(raw_frame) != frame_size:
                if time.time() - last_frame_time > FRAME_TIMEOUT:
                    restart_camera_stream.delay(camera_id)
                    return
                continue

            frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((360, 480, 3))
            _, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 60])

            # Store latest frame in Redis
            cache.set(FRAME_CACHE_KEY.format(camera_id=camera_id), jpeg.tobytes(), timeout=10)

            last_frame_time = time.time()

    except Exception as e:
        restart_camera_stream.delay(camera_id)
    finally:
        cleanup_camera_stream(camera_id)

# -----------------------------------------
# Celery Task: Restart Camera Stream
# -----------------------------------------
@shared_task(bind=True)
def restart_camera_stream(self, camera_id):
    """Restarts a camera stream if it fails."""
    cleanup_camera_stream(camera_id)
    time.sleep(2)  # Prevent rapid restart loops
    start_camera_stream.delay(camera_id)

# -----------------------------------------
# Celery Task: Cleanup Camera Stream
# -----------------------------------------
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
    cache.delete(FRAME_CACHE_KEY.format(camera_id=camera_id))