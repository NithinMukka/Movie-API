# pyrefly: ignore [missing-import]
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import relationship
from database import Base
import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="customer", nullable=False)  # customer | admin

    bookings = relationship("Booking", back_populates="user", cascade="all, delete-orphan", lazy="selectin")

class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String)
    show_time = Column(DateTime, default=datetime.datetime.utcnow)
    available_seats = Column(Integer, default=100)

    bookings = relationship("Booking", back_populates="movie", cascade="all, delete-orphan", lazy="selectin")

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    movie_id = Column(Integer, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    seats_booked = Column(Integer, nullable=False)
    booking_time = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    status = Column(String, default="CONFIRMED", nullable=False)  # CONFIRMED | CANCELLED

    user = relationship("User", back_populates="bookings", lazy="selectin")
    movie = relationship("Movie", back_populates="bookings", lazy="selectin")
