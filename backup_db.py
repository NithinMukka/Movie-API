import psycopg2
import datetime
import os
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
SQLALCHEMY_DATABASE_URL = settings.database_url

def backup_database():
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"backup_{timestamp}.sql"
    # This uses the pg_dump command (Postgres tool)
    # Ensure pg_dump is in your system PATH
    os.system(f"pg_dump {SQLALCHEMY_DATABASE_URL} > {filename}")
    print(f"Backup created: {filename}")

if __name__ == "__main__":
    backup_database()