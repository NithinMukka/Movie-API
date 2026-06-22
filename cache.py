import redis

# Use the 'rediss://' URL provided by your Upstash Dashboard
# Notice it's rediss (with two s's) for SSL
redis_url = "rediss://default:gQAAAAAAAbTHAAIgcDJiMGI3MDEzZDU1MGQ0ZWVmOTJhYWNiYjU3Y2QzNzE5MA@precious-swift-111815.upstash.io:6379"

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