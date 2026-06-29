from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str

    # --- JWT auth ---
    # IMPORTANT: set a real SECRET_KEY in .env for any non-local use.
    # Generate one with:  python -c "import secrets; print(secrets.token_hex(32))"
    secret_key: str = "dev-secret-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    class Config:
        env_file = ".env"

# Create a settings instance
settings = Settings()
