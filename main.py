from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from database import engine, get_db
import json
from cache import get_cache, set_cache, redis_client

# Create all tables in the database (automatically)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Movie Booking API")

@app.get("/")
def read_root():
    return {"message": "Welcome to the Movie Booking API! Go to /docs for the API documentation."}

# 1. CREATE: Add a new movie
@app.post("/movies/", response_model=schemas.MovieResponse)
def create_movie(movie: schemas.MovieCreate, db: Session = Depends(get_db)):
    db_movie = models.Movie(**movie.dict())
    db.add(db_movie)
    db.commit()
    redis_client.flushdb()
    # db.refresh(db_movie)
    return db_movie

# 2. READ: Get all movies
@app.get("/movies/", response_model=list[schemas.MovieResponse])
def read_movies(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    cache_key = f"movies_{skip}_{limit}"
    
    # 1. Try to get from Redis
    cached_data = get_cache(cache_key)
    if cached_data:
        print("Returning from Cache!")
        return json.loads(cached_data)
    
    # 2. If not in cache, query Postgres
    print("Querying Database...")
    movies = db.query(models.Movie).offset(skip).limit(limit).all()
    
    # 3. Save to Redis for next time
    # We convert objects to dicts because complex objects aren't JSON serializable
    movie_list = [movie.__dict__ for movie in movies]
    # Remove SQLAlchemy internal state from dict
    for m in movie_list: m.pop('_sa_instance_state', None)
    
    set_cache(cache_key, movie_list)
    
    return movies

# 3. READ: Get a single movie by ID
@app.get("/movies/{movie_id}", response_model=schemas.MovieResponse)
def read_movie(movie_id: int, db: Session = Depends(get_db)):
    movie = db.query(models.Movie).filter(models.Movie.id == movie_id).first()
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return movie

# 4. UPDATE: Update a movie's details
@app.put("/movies/{movie_id}", response_model=schemas.MovieResponse)
def update_movie(movie_id: int, movie_data: schemas.MovieCreate, db: Session = Depends(get_db)):
    movie = db.query(models.Movie).filter(models.Movie.id == movie_id).first()
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    for key, value in movie_data.dict().items():
        setattr(movie, key, value)
        
    db.commit()
    db.refresh(movie)
    return movie

# 5. DELETE: Remove a movie
@app.delete("/movies/{movie_id}")
def delete_movie(movie_id: int, db: Session = Depends(get_db)):
    movie = db.query(models.Movie).filter(models.Movie.id == movie_id).first()
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    db.delete(movie)
    db.commit()
    return {"message": "Movie deleted successfully"}