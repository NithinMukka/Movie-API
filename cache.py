import redis
from config import settings

# Now use it!
redis_url = settings.redis_url
# We use from_url to handle the connection string automatically
redis_client = redis.from_url(redis_url, decode_responses=True)

def get_cache(key):
    try:
        return redis_client.get(key)
    except Exception as e:
        print(f"Cache Error: {e}")
        return None

def set_cache(key, value, expire=60):
    try:
        import json
        redis_client.setex(key, expire, json.dumps(value))
    except Exception as e:
        print(f"Cache Error: {e}")

def invalidate_movie_cache():
    try:
        # Scan and delete keys matching 'movies_*' to prevent full database flush
        for key in redis_client.scan_iter("movies_*"):
            redis_client.delete(key)
        print("Invalidated cached movie data.")
    except Exception as e:
        print(f"Cache Invalidation Error: {e}")