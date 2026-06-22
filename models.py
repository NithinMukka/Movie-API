# pyrefly: ignore [missing-import]
from sqlalchemy import Column, Integer, String, DateTime
from database import Base
import datetime

class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String)
    show_time = Column(DateTime, default=datetime.datetime.utcnow)
    available_seats = Column(Integer, default=100)