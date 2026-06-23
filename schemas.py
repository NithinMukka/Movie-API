from pydantic import BaseModel, field_validator
from datetime import datetime, timezone
from typing import Optional

# Data expected from user to create/update a movie
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

# Data returned to the user
class MovieResponse(BaseModel):
    id: int
    title: str
    description: str
    show_time: datetime
    available_seats: int

    class Config:
        from_attributes = True