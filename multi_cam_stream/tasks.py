# from celery import shared_task
# import subprocess
# import numpy as np
# import cv2
# import time
# from django.core.cache import cache
# from .utils import store_frame  # Function for storing frames in Redis

# FRAME_TIMEOUT = 5  # Time before retrying FFmpeg

# @shared_task(bind=True)
# def stream_camera_ffmpeg(self, camera_id, camera_url, section_id):
#     """Starts an FFmpeg process for a camera and maintains frame queue using Redis."""

#     # Abort if section is not active
#     if cache.get("active_section") != str(section_id):
#         return  

#     ffmpeg_cmd = [
#         "ffmpeg", "-rtsp_transport", "tcp", "-i", camera_url,
#         "-an", "-vf", "fps=5,scale=640:480", "-f", "image2pipe",
#         "-pix_fmt", "bgr24", "-vcodec", "rawvideo", "-"
#     ]

#     process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8)
#     frame_size = 640 * 480 * 3
#     last_frame_time = time.time()

#     while process.poll() is None:
#         # If section is changed, terminate camera stream
#         if cache.get("active_section") != str(section_id):
#             process.terminate()
#             cache.delete(f"camera_active:{camera_id}")  # Remove camera's active flag
#             return

#         raw_frame = process.stdout.read(frame_size)
#         if len(raw_frame) != frame_size:
#             if time.time() - last_frame_time > FRAME_TIMEOUT:
#                 process.terminate()
#                 self.retry(countdown=5, max_retries=3)  # Retry if timeout
#                 return
#             continue

#         frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((480, 640, 3))
#         _, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])

#         store_frame(camera_id, jpeg.tobytes())  # Store frame in Redis
#         last_frame_time = time.time()

#     process.terminate()
#     cache.delete(f"camera_active:{camera_id}")  # Ensure camera flag is removed
