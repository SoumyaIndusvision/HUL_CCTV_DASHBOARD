import cv2
import time
import redis
import subprocess
import numpy as np
from celery import shared_task
from django.core.cache import cache
from .models import Camera

FRAME_TIMEOUT = 60  # Timeout for unresponsive cameras
REDIS_FRAME_KEY = "camera_stream:{camera_id}"

def store_frame(camera_id, frame):
    """Store the latest frame in Redis."""
    cache.set(REDIS_FRAME_KEY.format(camera_id=camera_id), frame, timeout=60)

def get_latest_frame(camera_id):
    """Retrieve the latest frame from Redis."""
    return cache.get(REDIS_FRAME_KEY.format(camera_id=camera_id))

@shared_task(bind=True)
def stream_camera_ffmpeg(self, camera_id, camera_url, section_id):
    """Starts an FFmpeg process for a camera and maintains frame queue using Redis."""
    
    current_active_section = cache.get("active_section")

    # If the section has changed, terminate the process
    if current_active_section and current_active_section != section_id:
        return

    ffmpeg_cmd = [
        "ffmpeg", "-rtsp_transport", "tcp", "-i", camera_url,
        "-an", "-vf", "fps=5,scale=640:480", "-f", "image2pipe",
        "-pix_fmt", "bgr24", "-vcodec", "rawvideo", "-"
    ]

    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8)
    frame_size = 640 * 480 * 3
    last_frame_time = time.time()

    while process.poll() is None:
        # Check if section changed mid-stream
        if cache.get("active_section") != section_id:
            process.terminate()
            return

        raw_frame = process.stdout.read(frame_size)
        if len(raw_frame) != frame_size:
            if time.time() - last_frame_time > FRAME_TIMEOUT:
                process.terminate()
                self.retry(countdown=5, max_retries=3)  # Retry task
                return
            continue

        frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((480, 640, 3))
        _, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])

        store_frame(camera_id, jpeg.tobytes())
        last_frame_time = time.time()

    process.terminate()
