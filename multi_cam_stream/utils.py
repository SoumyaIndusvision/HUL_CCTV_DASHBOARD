# import redis

# redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

# def store_frame(camera_id, frame_data):
#     """Stores the latest frame for a given camera in Redis."""
#     redis_client.set(f"camera_frame:{camera_id}", frame_data)
