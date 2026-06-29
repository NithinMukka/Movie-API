"""
Real concurrency tests — require Postgres (SQLite ignores SELECT ... FOR UPDATE).

These fire genuinely parallel requests at the same seat and assert that the
row-locking lets exactly one win. Auto-skipped when the test DB isn't running.
"""
import asyncio
import pytest

pytestmark = pytest.mark.postgres

SHOW_PRICE = "200.00"


async def _setup_show(client, admin_headers, num_seats=3):
    theatre = (await client.post("/theatres/", headers=admin_headers,
                                 json={"name": "PVR", "city": "Hyderabad"})).json()
    screen = (await client.post(f"/theatres/{theatre['id']}/screens/", headers=admin_headers,
                                json={"name": "Screen 1"})).json()
    seat_ids = []
    for n in range(1, num_seats + 1):
        seat = (await client.post(f"/screens/{screen['id']}/seats/", headers=admin_headers,
                                  json={"row": "A", "number": n})).json()
        seat_ids.append(seat["id"])
    movie = (await client.post("/movies/", headers=admin_headers,
                               json={"title": "Tenet", "description": "Time",
                                     "duration_mins": 150})).json()
    show = (await client.post("/shows/", headers=admin_headers,
                              json={"movie_id": movie["id"], "screen_id": screen["id"],
                                    "start_time": "2030-01-01T18:00:00", "price": SHOW_PRICE})).json()
    return {"show_id": show["id"], "seat_ids": seat_ids}


async def _register_and_token(client, email):
    await client.post("/auth/register",
                      json={"name": email, "email": email, "password": "pw123456"})
    login = await client.post("/auth/login", data={"username": email, "password": "pw123456"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def test_parallel_hold_exactly_one_winner(pg_client, pg_admin_headers):
    """10 users race for the SAME seat — exactly one hold succeeds."""
    ctx = await _setup_show(pg_client, pg_admin_headers)
    target_seat = ctx["seat_ids"][0]

    N = 10
    customers = [await _register_and_token(pg_client, f"racer{i}@test.com") for i in range(N)]

    async def attempt(headers):
        r = await pg_client.post(f"/shows/{ctx['show_id']}/hold", headers=headers,
                                 json={"seat_ids": [target_seat]})
        return r.status_code

    results = await asyncio.gather(*(attempt(h) for h in customers))

    assert results.count(200) == 1, f"expected exactly one winner, got {results}"
    assert results.count(409) == N - 1

    # The seat is HELD exactly once.
    seats = (await pg_client.get(f"/shows/{ctx['show_id']}/seats/")).json()
    held = [s for s in seats if s["seat_id"] == target_seat and s["status"] == "HELD"]
    assert len(held) == 1


async def test_parallel_booking_no_oversell(pg_client, pg_admin_headers):
    """Two confirmations race for the same held seat — no double-booking."""
    ctx = await _setup_show(pg_client, pg_admin_headers)
    cust = await _register_and_token(pg_client, "buyer@test.com")

    hold = await pg_client.post(f"/shows/{ctx['show_id']}/hold", headers=cust,
                                json={"seat_ids": [ctx["seat_ids"][0]]})
    show_seat_ids = hold.json()["show_seat_ids"]

    async def confirm():
        r = await pg_client.post("/bookings/", headers=cust,
                                 json={"show_id": ctx["show_id"], "show_seat_ids": show_seat_ids})
        return r.status_code

    results = await asyncio.gather(confirm(), confirm())

    assert results.count(200) == 1, f"expected exactly one booking, got {results}"
    assert results.count(409) == 1

    # Seat is BOOKED, and the customer has exactly one booking.
    seats = (await pg_client.get(f"/shows/{ctx['show_id']}/seats/")).json()
    booked = [s for s in seats if s["status"] == "BOOKED"]
    assert len(booked) == 1

    my_bookings = (await pg_client.get("/bookings/", headers=cust)).json()
    assert len(my_bookings) == 1


async def test_parallel_hold_distinct_seats_all_succeed(pg_client, pg_admin_headers):
    """Holds on different seats don't block each other — all succeed."""
    ctx = await _setup_show(pg_client, pg_admin_headers, num_seats=3)
    customers = [await _register_and_token(pg_client, f"multi{i}@test.com") for i in range(3)]

    async def attempt(headers, seat_id):
        r = await pg_client.post(f"/shows/{ctx['show_id']}/hold", headers=headers,
                                 json={"seat_ids": [seat_id]})
        return r.status_code

    results = await asyncio.gather(
        *(attempt(h, s) for h, s in zip(customers, ctx["seat_ids"]))
    )
    assert results == [200, 200, 200]
