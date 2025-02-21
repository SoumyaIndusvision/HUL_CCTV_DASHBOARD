import os
import redis
import signal
from django.core.cache import cache

redis_client = redis.Redis(host="localhost", port=6379, db=1)

def cleanup_camera_streams(*args):
    """Terminates all active FFmpeg processes."""
    print("Shutting down all camera streams...")

    active_cameras = cache.keys("camera_active:*")
    for key in active_cameras:
        cache.delete(key)

    os.system("pkill -f ffmpeg")  # Kill all FFmpeg processes
    exit(0)

# Register cleanup on Django shutdown
signal.signal(signal.SIGINT, cleanup_camera_streams)
signal.signal(signal.SIGTERM, cleanup_camera_streams)
