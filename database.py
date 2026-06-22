from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
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

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get the DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()