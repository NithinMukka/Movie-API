# Scalable Movie Booking API

A high-performance Movie Booking API built with FastAPI, PostgreSQL, and Redis.

## Features
- **CRUD Operations:** Create, Read, Update, and Delete movie records.
- **Performance:** Redis caching implemented for lightning-fast read operations.
- **Containerization:** Fully Dockerized for seamless deployment.
- **Data Integrity:** PostgreSQL with SQLAlchemy ORM.

## Tech Stack
- Python, FastAPI
- PostgreSQL (Neon.tech)
- Redis (Upstash)
- Docker

## Testing

The suite has two tiers:

- **Fast tier (SQLite, in-memory):** auth and booking-flow logic. Needs nothing running.
- **Concurrency tier (real Postgres):** proves seat-locking (`SELECT … FOR UPDATE`)
  prevents double-booking under genuinely parallel requests. SQLite can't test this
  because it ignores row locks, so these tests run against a throwaway Postgres.

```bash
# Fast tier only (no database required)
pytest -m "not postgres"

# Concurrency tier — start the throwaway Postgres first
docker compose -f docker-compose.test.yml up -d
pytest -m postgres
docker compose -f docker-compose.test.yml down

# Everything (Postgres tests auto-skip if the DB isn't up)
pytest
```

The test Postgres URL defaults to the local Docker instance and can be overridden
with the `TEST_DATABASE_URL` environment variable.

## Database migrations

Schema is managed by Alembic (not auto-created at startup):

```bash
alembic upgrade head            # apply migrations
alembic revision --autogenerate -m "describe change"
```

## Deployment
Deployed on Render. Access the API documentation here: https://movie-api-5jid.onrender.com/docs

