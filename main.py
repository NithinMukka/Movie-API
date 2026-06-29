import datetime
import json

from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
# pyrefly: ignore [missing-import]
from sqlalchemy.ext.asyncio import AsyncSession
# pyrefly: ignore [missing-import]
from sqlalchemy.future import select

import models
import schemas
from database import get_db
from cache import get_cache, set_cache, invalidate_movie_cache
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_admin,
)

SEAT_HOLD_MINUTES = 10

app = FastAPI(title="Movie Booking API")

# Schema/DDL is managed by Alembic — run `alembic upgrade head` to create tables.
# We deliberately do NOT create_all on startup so the running schema can't drift
# from the migration history.


@app.get("/")
async def read_root():
    return {"message": "Movie Booking API"}


# ---------------------------------------------------------------------------
# AUTH
# ---------------------------------------------------------------------------

@app.post("/auth/register", response_model=schemas.UserResponse)
async def register(user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User).filter(models.User.email == user.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")

    db_user = models.User(
        name=user.name,
        email=user.email,
        password_hash=hash_password(user.password),
        role="customer",  # never trust client-supplied role
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


@app.post("/auth/login", response_model=schemas.Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    # OAuth2PasswordRequestForm uses 'username'; we treat it as email.
    result = await db.execute(select(models.User).filter(models.User.email == form_data.username))
    user = result.scalars().first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return {"access_token": create_access_token(str(user.id)), "token_type": "bearer"}


# ---------------------------------------------------------------------------
# USERS
# ---------------------------------------------------------------------------

@app.get("/users/me", response_model=schemas.UserResponse)
async def read_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@app.get("/users/", response_model=list[schemas.UserResponse])
async def read_users(
    skip: int = 0, limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    result = await db.execute(select(models.User).offset(skip).limit(limit))
    return result.scalars().all()


@app.get("/users/{user_id}", response_model=schemas.UserResponse)
async def read_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    result = await db.execute(select(models.User).filter(models.User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ---------------------------------------------------------------------------
# MOVIES  (admin write, public read)
# ---------------------------------------------------------------------------

@app.post("/movies/", response_model=schemas.MovieResponse)
async def create_movie(
    movie: schemas.MovieCreate,
    db: AsyncSession = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    db_movie = models.Movie(**movie.model_dump())
    db.add(db_movie)
    await db.commit()
    await db.refresh(db_movie)
    invalidate_movie_cache()
    return db_movie


@app.get("/movies/", response_model=list[schemas.MovieResponse])
async def read_movies(skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db)):
    cache_key = f"movies_{skip}_{limit}"
    cached = get_cache(cache_key)
    if cached:
        return json.loads(cached)

    result = await db.execute(select(models.Movie).offset(skip).limit(limit))
    movies = result.scalars().all()
    movie_list = [
        {"id": m.id, "title": m.title, "description": m.description, "duration_mins": m.duration_mins}
        for m in movies
    ]
    set_cache(cache_key, movie_list)
    return movies


@app.get("/movies/{movie_id}", response_model=schemas.MovieResponse)
async def read_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Movie).filter(models.Movie.id == movie_id))
    movie = result.scalars().first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    return movie


@app.put("/movies/{movie_id}", response_model=schemas.MovieResponse)
async def update_movie(
    movie_id: int,
    movie_data: schemas.MovieCreate,
    db: AsyncSession = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    result = await db.execute(select(models.Movie).filter(models.Movie.id == movie_id))
    movie = result.scalars().first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    for key, value in movie_data.model_dump().items():
        setattr(movie, key, value)
    await db.commit()
    await db.refresh(movie)
    invalidate_movie_cache()
    return movie


@app.delete("/movies/{movie_id}")
async def delete_movie(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    result = await db.execute(select(models.Movie).filter(models.Movie.id == movie_id))
    movie = result.scalars().first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    await db.delete(movie)
    await db.commit()
    invalidate_movie_cache()
    return {"message": "Movie deleted"}


# ---------------------------------------------------------------------------
# THEATRES  (admin write, public read)
# ---------------------------------------------------------------------------

@app.post("/theatres/", response_model=schemas.TheatreResponse)
async def create_theatre(
    theatre: schemas.TheatreCreate,
    db: AsyncSession = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    db_theatre = models.Theatre(**theatre.model_dump())
    db.add(db_theatre)
    await db.commit()
    await db.refresh(db_theatre)
    return db_theatre


@app.get("/theatres/", response_model=list[schemas.TheatreResponse])
async def read_theatres(skip: int = 0, limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Theatre).offset(skip).limit(limit))
    return result.scalars().all()


@app.get("/theatres/{theatre_id}", response_model=schemas.TheatreResponse)
async def read_theatre(theatre_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Theatre).filter(models.Theatre.id == theatre_id))
    theatre = result.scalars().first()
    if not theatre:
        raise HTTPException(status_code=404, detail="Theatre not found")
    return theatre


# ---------------------------------------------------------------------------
# SCREENS  (admin write, public read)
# ---------------------------------------------------------------------------

@app.post("/theatres/{theatre_id}/screens/", response_model=schemas.ScreenResponse)
async def create_screen(
    theatre_id: int,
    screen: schemas.ScreenCreate,
    db: AsyncSession = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    result = await db.execute(select(models.Theatre).filter(models.Theatre.id == theatre_id))
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Theatre not found")
    db_screen = models.Screen(theatre_id=theatre_id, **screen.model_dump())
    db.add(db_screen)
    await db.commit()
    await db.refresh(db_screen)
    return db_screen


@app.get("/theatres/{theatre_id}/screens/", response_model=list[schemas.ScreenResponse])
async def read_screens(theatre_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.Screen).filter(models.Screen.theatre_id == theatre_id)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# SEATS  (admin write, public read)
# ---------------------------------------------------------------------------

@app.post("/screens/{screen_id}/seats/", response_model=schemas.SeatResponse)
async def create_seat(
    screen_id: int,
    seat: schemas.SeatCreate,
    db: AsyncSession = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    result = await db.execute(select(models.Screen).filter(models.Screen.id == screen_id))
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Screen not found")
    db_seat = models.Seat(screen_id=screen_id, **seat.model_dump())
    db.add(db_seat)
    await db.commit()
    await db.refresh(db_seat)
    return db_seat


@app.get("/screens/{screen_id}/seats/", response_model=list[schemas.SeatResponse])
async def read_seats(screen_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.Seat).filter(models.Seat.screen_id == screen_id)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# SHOWS  (admin write, public read)
# ---------------------------------------------------------------------------

@app.post("/shows/", response_model=schemas.ShowResponse)
async def create_show(
    show: schemas.ShowCreate,
    db: AsyncSession = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    # Validate movie and screen exist.
    movie_res = await db.execute(select(models.Movie).filter(models.Movie.id == show.movie_id))
    if not movie_res.scalars().first():
        raise HTTPException(status_code=404, detail="Movie not found")

    screen_res = await db.execute(select(models.Screen).filter(models.Screen.id == show.screen_id))
    screen = screen_res.scalars().first()
    if not screen:
        raise HTTPException(status_code=404, detail="Screen not found")

    db_show = models.Show(**show.model_dump())
    db.add(db_show)
    await db.flush()  # get db_show.id before creating show_seats

    # Materialise one ShowSeat row per physical seat on this screen.
    seats_res = await db.execute(
        select(models.Seat).filter(models.Seat.screen_id == show.screen_id)
    )
    seats = seats_res.scalars().all()
    for seat in seats:
        db.add(models.ShowSeat(show_id=db_show.id, seat_id=seat.id))

    await db.commit()
    await db.refresh(db_show)
    return db_show


@app.get("/shows/", response_model=list[schemas.ShowResponse])
async def read_shows(
    movie_id: int | None = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    query = select(models.Show)
    if movie_id:
        query = query.filter(models.Show.movie_id == movie_id)
    result = await db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()


@app.get("/shows/{show_id}", response_model=schemas.ShowResponse)
async def read_show(show_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Show).filter(models.Show.id == show_id))
    show = result.scalars().first()
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    return show


@app.get("/shows/{show_id}/seats/", response_model=list[schemas.ShowSeatResponse])
async def read_show_seats(show_id: int, db: AsyncSession = Depends(get_db)):
    """Returns every seat for a show with its current availability status."""
    result = await db.execute(
        select(models.ShowSeat).filter(models.ShowSeat.show_id == show_id)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# HOLD  —  reserve seats for SEAT_HOLD_MINUTES before payment
# ---------------------------------------------------------------------------

@app.post("/shows/{show_id}/hold", response_model=schemas.HoldResponse)
async def hold_seats(
    show_id: int,
    body: schemas.HoldRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not body.seat_ids:
        raise HTTPException(status_code=400, detail="No seats requested")

    # SELECT … FOR UPDATE locks these rows; concurrent requests wait here.
    result = await db.execute(
        select(models.ShowSeat)
        .filter(
            models.ShowSeat.show_id == show_id,
            models.ShowSeat.seat_id.in_(body.seat_ids),
        )
        .with_for_update()
    )
    show_seats = result.scalars().all()

    if len(show_seats) != len(body.seat_ids):
        raise HTTPException(status_code=404, detail="One or more seats not found for this show")

    now = datetime.datetime.utcnow()
    unavailable = [
        s for s in show_seats
        if s.status == models.ShowSeatStatus.BOOKED
        or (s.status == models.ShowSeatStatus.HELD and s.held_until and s.held_until > now)
    ]
    if unavailable:
        raise HTTPException(status_code=409, detail="One or more seats are unavailable")

    held_until = now + datetime.timedelta(minutes=SEAT_HOLD_MINUTES)
    for s in show_seats:
        s.status = models.ShowSeatStatus.HELD
        s.held_until = held_until

    await db.commit()

    return {
        "show_seat_ids": [s.id for s in show_seats],
        "held_until": held_until,
    }


# ---------------------------------------------------------------------------
# BOOKINGS  —  confirm a hold
# ---------------------------------------------------------------------------

@app.post("/bookings/", response_model=schemas.BookingResponse)
async def create_booking(
    booking: schemas.BookingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Re-lock the held ShowSeat rows to confirm atomically.
    result = await db.execute(
        select(models.ShowSeat)
        .filter(models.ShowSeat.id.in_(booking.show_seat_ids))
        .with_for_update()
    )
    show_seats = result.scalars().all()

    if len(show_seats) != len(booking.show_seat_ids):
        raise HTTPException(status_code=404, detail="One or more show seats not found")

    now = datetime.datetime.utcnow()
    for s in show_seats:
        if s.show_id != booking.show_id:
            raise HTTPException(status_code=400, detail="Seat does not belong to this show")
        if s.status != models.ShowSeatStatus.HELD or (s.held_until and s.held_until < now):
            raise HTTPException(status_code=409, detail="Hold expired or seat no longer held")

    # Fetch price from the show.
    show_res = await db.execute(select(models.Show).filter(models.Show.id == booking.show_id))
    show = show_res.scalars().first()
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    total = show.price * len(show_seats)

    db_booking = models.Booking(
        user_id=current_user.id,
        show_id=booking.show_id,
        total_amount=total,
        status="CONFIRMED",
    )
    db.add(db_booking)
    await db.flush()

    for s in show_seats:
        s.status = models.ShowSeatStatus.BOOKED
        s.held_until = None
        db.add(models.BookingSeat(booking_id=db_booking.id, show_seat_id=s.id))

    await db.commit()

    # Re-query so the `seats` relationship is eager-loaded (selectin).
    # A bare refresh() only reloads columns, so serializing BookingResponse.seats
    # would otherwise trigger an async lazy-load on an unloaded collection.
    result = await db.execute(select(models.Booking).filter(models.Booking.id == db_booking.id))
    return result.scalars().first()


@app.get("/bookings/", response_model=list[schemas.BookingResponse])
async def read_bookings(
    skip: int = 0, limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = select(models.Booking)
    if current_user.role != "admin":
        query = query.filter(models.Booking.user_id == current_user.id)
    result = await db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()


@app.get("/bookings/{booking_id}", response_model=schemas.BookingResponse)
async def read_booking(
    booking_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    result = await db.execute(select(models.Booking).filter(models.Booking.id == booking_id))
    booking = result.scalars().first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if current_user.role != "admin" and booking.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your booking")
    return booking


@app.post("/bookings/{booking_id}/cancel", response_model=schemas.BookingResponse)
async def cancel_booking(
    booking_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    result = await db.execute(select(models.Booking).filter(models.Booking.id == booking_id))
    booking = result.scalars().first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if current_user.role != "admin" and booking.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your booking")
    if booking.status == "CANCELLED":
        raise HTTPException(status_code=400, detail="Booking already cancelled")

    # Return all seats to AVAILABLE.
    for bs in booking.seats:
        show_seat = bs.show_seat
        show_seat.status = models.ShowSeatStatus.AVAILABLE
        show_seat.held_until = None

    booking.status = "CANCELLED"
    await db.commit()
    await db.refresh(booking)
    return booking
