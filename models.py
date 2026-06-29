# pyrefly: ignore [missing-import]
import datetime
import enum
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey,
    Numeric, Enum, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from database import Base


class Theatre(Base):
    __tablename__ = "theatres"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    city = Column(String, index=True, nullable=False)

    screens = relationship("Screen", back_populates="theatre", cascade="all, delete-orphan", lazy="selectin")


class Screen(Base):
    __tablename__ = "screens"

    id = Column(Integer, primary_key=True, index=True)
    theatre_id = Column(Integer, ForeignKey("theatres.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)  # e.g. "Screen 1", "IMAX"

    theatre = relationship("Theatre", back_populates="screens")
    seats = relationship("Seat", back_populates="screen", cascade="all, delete-orphan", lazy="selectin")
    shows = relationship("Show", back_populates="screen", cascade="all, delete-orphan")


class SeatType(str, enum.Enum):
    REGULAR = "REGULAR"
    PREMIUM = "PREMIUM"
    RECLINER = "RECLINER"


class Seat(Base):
    """Physical seat defined once per screen; reused across all shows on that screen."""
    __tablename__ = "seats"

    id = Column(Integer, primary_key=True, index=True)
    screen_id = Column(Integer, ForeignKey("screens.id", ondelete="CASCADE"), nullable=False)
    row = Column(String, nullable=False)      # e.g. "A"
    number = Column(Integer, nullable=False)  # e.g. 5  ->  seat "A5"
    seat_type = Column(Enum(SeatType), default=SeatType.REGULAR, nullable=False)

    screen = relationship("Screen", back_populates="seats")

    __table_args__ = (
        UniqueConstraint("screen_id", "row", "number", name="uq_seat_in_screen"),
    )


class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    description = Column(String)
    duration_mins = Column(Integer, nullable=False)

    shows = relationship("Show", back_populates="movie", cascade="all, delete-orphan")


class Show(Base):
    """One screening of a movie on a particular screen at a specific time."""
    __tablename__ = "shows"

    id = Column(Integer, primary_key=True, index=True)
    movie_id = Column(Integer, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    screen_id = Column(Integer, ForeignKey("screens.id", ondelete="CASCADE"), nullable=False)
    start_time = Column(DateTime, nullable=False, index=True)
    price = Column(Numeric(10, 2), nullable=False)

    movie = relationship("Movie", back_populates="shows")
    screen = relationship("Screen", back_populates="shows")
    show_seats = relationship("ShowSeat", back_populates="show", cascade="all, delete-orphan", lazy="selectin")


class ShowSeatStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    HELD = "HELD"      # temporarily reserved during checkout; expires after held_until
    BOOKED = "BOOKED"


class ShowSeat(Base):
    """
    The concurrency crux: one row per (show, physical seat).
    Status here is the single source of truth for availability.
    The unique constraint makes double-booking impossible at the DB level.
    """
    __tablename__ = "show_seats"

    id = Column(Integer, primary_key=True, index=True)
    show_id = Column(Integer, ForeignKey("shows.id", ondelete="CASCADE"), nullable=False)
    seat_id = Column(Integer, ForeignKey("seats.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum(ShowSeatStatus), default=ShowSeatStatus.AVAILABLE, nullable=False, index=True)
    held_until = Column(DateTime, nullable=True)  # set when status = HELD; cleared on book/expire

    show = relationship("Show", back_populates="show_seats")
    seat = relationship("Seat", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("show_id", "seat_id", name="uq_seat_per_show"),
    )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="customer", nullable=False)  # customer | admin

    bookings = relationship("Booking", back_populates="user", cascade="all, delete-orphan", lazy="selectin")


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    show_id = Column(Integer, ForeignKey("shows.id", ondelete="CASCADE"), nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String, default="CONFIRMED", nullable=False)  # CONFIRMED | CANCELLED
    booking_time = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="bookings")
    show = relationship("Show")
    seats = relationship("BookingSeat", back_populates="booking", cascade="all, delete-orphan", lazy="selectin")


class BookingSeat(Base):
    """Links a booking to the specific ShowSeat rows it holds."""
    __tablename__ = "booking_seats"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    show_seat_id = Column(Integer, ForeignKey("show_seats.id", ondelete="CASCADE"), nullable=False)

    booking = relationship("Booking", back_populates="seats")
    show_seat = relationship("ShowSeat", lazy="selectin")
