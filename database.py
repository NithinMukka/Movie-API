from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Format: postgresql://<username>:<password>@localhost/<dbname>
# If using Neon.tech, paste your provided connection string here.
SQLALCHEMY_DATABASE_URL = "postgresql://neondb_owner:npg_i1SGmv3azwOH@ep-royal-dew-aq9ups96.c-8.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

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