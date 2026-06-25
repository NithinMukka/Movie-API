from fastapi import FastAPI, Depends, HTTPException
# pyrefly: ignore [missing-import]
from sqlalchemy.ext.asyncio import AsyncSession
# pyrefly: ignore [missing-import]
from sqlalchemy.future import select
import models, schemas
from database import engine, get_db, Base
import json
from cache import get_cache, set_cache, invalidate_movie_cache
import hashlib

# Initialize the app
app = FastAPI(title="Movie Booking API")

# Create tables on startup
@app.on_event("startup")
async def startup_event():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Movie Booking API (Async Version)!"}

# 1. CREATE: Add a new movie
@app.post("/movies/", response_model=schemas.MovieResponse)
async def create_movie(movie: schemas.MovieCreate, db: AsyncSession = Depends(get_db)):
    db_movie = models.Movie(**movie.dict())
    db.add(db_movie)
    await db.commit()
    await db.refresh(db_movie)
    
    # Invalidate cache
    invalidate_movie_cache() 
    return db_movie

# 2. READ: Get all movies (with Caching)
@app.get("/movies/", response_model=list[schemas.MovieResponse])
async def read_movies(skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db)):
    cache_key = f"movies_{skip}_{limit}"
    
    # Check cache
    cached_data = get_cache(cache_key)
    if cached_data:
        return json.loads(cached_data)
    
    # Query database
    result = await db.execute(select(models.Movie).offset(skip).limit(limit))
    movies = result.scalars().all()
    
    # Convert to dict for caching
    movie_list = [
        {"id": m.id, "title": m.title, "description": m.description, 
         "show_time": str(m.show_time), "available_seats": m.available_seats} 
        for m in movies
    ]
    
    set_cache(cache_key, movie_list)
    return movies

# 3. READ: Get a single movie by ID
@app.get("/movies/{movie_id}", response_model=schemas.MovieResponse)
async def read_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Movie).filter(models.Movie.id == movie_id))
    movie = result.scalars().first()
    
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return movie

# 4. DELETE: Remove a movie
@app.delete("/movies/{movie_id}")
async def delete_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Movie).filter(models.Movie.id == movie_id))
    movie = result.scalars().first()
    
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    await db.delete(movie)
    await db.commit()
    
    invalidate_movie_cache()
    return {"message": "Movie deleted successfully"}

# 5. UPDATE: Update a movie's details
@app.put("/movies/{movie_id}", response_model=schemas.MovieResponse)
async def update_movie(movie_id: int, movie_data: schemas.MovieCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Movie).filter(models.Movie.id == movie_id))
    movie = result.scalars().first()
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    for key, value in movie_data.dict().items():
        setattr(movie, key, value)
    await db.commit()
    await db.refresh(movie)
    invalidate_movie_cache()
    return movie


# Helper function for password hashing
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# --- USER ENDPOINTS ---

@app.post("/users/", response_model=schemas.UserResponse)
async def create_user(user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User).filter(models.User.email == user.email))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    db_user = models.User(
        name=user.name,
        email=user.email,
        password_hash=hash_password(user.password),
        role=user.role
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@app.get("/users/", response_model=list[schemas.UserResponse])
async def read_users(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User).offset(skip).limit(limit))
    return result.scalars().all()

@app.get("/users/{user_id}", response_model=schemas.UserResponse)
async def read_user(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User).filter(models.User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# --- BOOKING ENDPOINTS ---

@app.post("/bookings/", response_model=schemas.BookingResponse)
async def create_booking(booking: schemas.BookingCreate, db: AsyncSession = Depends(get_db)):
    # Validate user exists
    user_result = await db.execute(select(models.User).filter(models.User.id == booking.user_id))
    user = user_result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Validate movie exists
    movie_result = await db.execute(select(models.Movie).filter(models.Movie.id == booking.movie_id))
    movie = movie_result.scalars().first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    # Validate available seats
    if movie.available_seats < booking.seats_booked:
        raise HTTPException(status_code=400, detail="Not enough available seats")
    
    # Deduct seats and create booking
    movie.available_seats -= booking.seats_booked
    db_booking = models.Booking(
        user_id=booking.user_id,
        movie_id=booking.movie_id,
        seats_booked=booking.seats_booked,
        status="CONFIRMED"
    )
    db.add(db_booking)
    await db.commit()
    await db.refresh(db_booking)
    
    # Invalidate movie cache
    invalidate_movie_cache()
    
    return db_booking

@app.get("/bookings/", response_model=list[schemas.BookingResponse])
async def read_bookings(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Booking).offset(skip).limit(limit))
    return result.scalars().all()

@app.get("/bookings/{booking_id}", response_model=schemas.BookingResponse)
async def read_booking(booking_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Booking).filter(models.Booking.id == booking_id))
    booking = result.scalars().first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking

@app.post("/bookings/{booking_id}/cancel", response_model=schemas.BookingResponse)
async def cancel_booking(booking_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Booking).filter(models.Booking.id == booking_id))
    booking = result.scalars().first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.status == "CANCELLED":
        raise HTTPException(status_code=400, detail="Booking is already cancelled")
    
    # Restore movie seats
    movie_result = await db.execute(select(models.Movie).filter(models.Movie.id == booking.movie_id))
    movie = movie_result.scalars().first()
    if movie:
        movie.available_seats += booking.seats_booked
    
    booking.status = "CANCELLED"
    await db.commit()
    await db.refresh(booking)
    
    # Invalidate movie cache
    invalidate_movie_cache()
    
    return booking