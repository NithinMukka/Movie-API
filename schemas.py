from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# Data expected from user to create/update a movie
class MovieCreate(BaseModel):
    title: str
    description: str
    show_time: datetime
    available_seats: int

# Data returned to the user
class MovieResponse(BaseModel):
    id: int
    title: str
    description: str
    show_time: datetime
    available_seats: int

    class Config:
        from_attributes = True