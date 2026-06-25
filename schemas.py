from pydantic import BaseModel, field_validator
from datetime import datetime, timezone
from typing import Optional

# Movie schemas
class MovieCreate(BaseModel):
    title: str
    description: str
    show_time: datetime
    available_seats: int

    @field_validator("show_time")
    @classmethod
    def make_show_time_naive(cls, v: datetime) -> datetime:
        if v.tzinfo is not None:
            return v.astimezone(timezone.utc).replace(tzinfo=None)
        return v

class MovieResponse(BaseModel):
    id: int
    title: str
    description: str
    show_time: datetime
    available_seats: int

    class Config:
        from_attributes = True

# User schemas
class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: Optional[str] = "customer"

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str

    class Config:
        from_attributes = True

# Booking schemas
class BookingCreate(BaseModel):
    user_id: int
    movie_id: int
    seats_booked: int

class BookingResponse(BaseModel):
    id: int
    user_id: int
    movie_id: int
    seats_booked: int
    booking_time: datetime
    status: str

    class Config:
        from_attributes = True