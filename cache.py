import redis
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    database_url: str
    redis_url: str

    class Config:
        env_file = ".env"

# Create a settings instance
settings = Settings()

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