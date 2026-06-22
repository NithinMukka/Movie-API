# pyrefly: ignore [missing-import]
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import sessionmaker, declarative_base
from config import settings


# Your URL should now look like: 
# postgresql+asyncpg://user:password@host/db
DATABASE_URL = settings.database_url

# CHANGE THIS PART:
# asyncpg uses 'ssl' instead of 'sslmode'
engine = create_async_engine(
    DATABASE_URL, 
    echo=True,
    connect_args={"ssl": "require"} 
)

SessionLocal = sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with SessionLocal() as session:
        yield session
        # Note: We commit inside the endpoints, not here!