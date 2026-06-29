from pydantic import BaseModel, field_validator, EmailStr, Field
from datetime import datetime, timezone
from typing import Optional, Literal
from decimal import Decimal


# --- Auth ---

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- User ---

class UserCreate(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr                      # rejects malformed addresses, e.g. "abc"
    password: str = Field(min_length=8)  # minimum length enforced at the API edge

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str

    class Config:
        from_attributes = True


# --- Theatre ---

class TheatreCreate(BaseModel):
    name: str
    city: str

class TheatreResponse(BaseModel):
    id: int
    name: str
    city: str

    class Config:
        from_attributes = True


# --- Screen ---

class ScreenCreate(BaseModel):
    name: str

class ScreenResponse(BaseModel):
    id: int
    theatre_id: int
    name: str

    class Config:
        from_attributes = True


# --- Seat ---

class SeatCreate(BaseModel):
    row: str
    number: int
    seat_type: Literal["REGULAR", "PREMIUM", "RECLINER"] = "REGULAR"

class SeatResponse(BaseModel):
    id: int
    screen_id: int
    row: str
    number: int
    seat_type: str

    class Config:
        from_attributes = True


# --- Movie ---

class MovieCreate(BaseModel):
    title: str
    description: str
    duration_mins: int

class MovieResponse(BaseModel):
    id: int
    title: str
    description: str
    duration_mins: int

    class Config:
        from_attributes = True


# --- Show ---

class ShowCreate(BaseModel):
    movie_id: int
    screen_id: int
    start_time: datetime
    price: Decimal

    @field_validator("start_time")
    @classmethod
    def make_naive(cls, v: datetime) -> datetime:
        if v.tzinfo is not None:
            return v.astimezone(timezone.utc).replace(tzinfo=None)
        return v

class ShowResponse(BaseModel):
    id: int
    movie_id: int
    screen_id: int
    start_time: datetime
    price: Decimal

    class Config:
        from_attributes = True


# --- ShowSeat ---

class ShowSeatResponse(BaseModel):
    id: int
    show_id: int
    seat_id: int
    status: str
    held_until: Optional[datetime]

    class Config:
        from_attributes = True


# --- Hold ---

class HoldRequest(BaseModel):
    seat_ids: list[int]  # physical seat IDs to hold for this show

class HoldResponse(BaseModel):
    show_seat_ids: list[int]
    held_until: datetime


# --- Booking ---

class BookingCreate(BaseModel):
    show_id: int
    show_seat_ids: list[int]  # ShowSeat IDs obtained from the hold step

class BookingSeatResponse(BaseModel):
    id: int
    show_seat_id: int

    class Config:
        from_attributes = True

class BookingResponse(BaseModel):
    id: int
    user_id: int
    show_id: int
    total_amount: Decimal
    status: str
    booking_time: datetime
    seats: list[BookingSeatResponse]

    class Config:
        from_attributes = True
