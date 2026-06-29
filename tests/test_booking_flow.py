"""
End-to-end booking flow:
theatre -> screen -> seats -> movie -> show -> hold -> book -> cancel,
plus the concurrency-relevant conflict (a held/booked seat can't be re-held).
"""
import pytest

SHOW_PRICE = "200.00"


async def _setup_show(client, admin_headers, num_seats=3):
    """Build a theatre/screen/seats/movie/show as admin. Returns ids."""
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
                               json={"title": "Inception", "description": "Dreams",
                                     "duration_mins": 148})).json()
    show = (await client.post("/shows/", headers=admin_headers,
                              json={"movie_id": movie["id"], "screen_id": screen["id"],
                                    "start_time": "2030-01-01T18:00:00",
                                    "price": SHOW_PRICE})).json()
    return {"show_id": show["id"], "screen_id": screen["id"], "seat_ids": seat_ids}


async def _register_and_token(client, email):
    await client.post("/auth/register",
                      json={"name": email, "email": email, "password": "pw123456"})
    login = await client.post("/auth/login", data={"username": email, "password": "pw123456"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def test_show_creation_materializes_seats(client, admin_headers):
    ctx = await _setup_show(client, admin_headers, num_seats=3)
    seats = (await client.get(f"/shows/{ctx['show_id']}/seats/")).json()
    assert len(seats) == 3
    assert all(s["status"] == "AVAILABLE" for s in seats)


async def test_hold_then_book(client, admin_headers):
    ctx = await _setup_show(client, admin_headers)
    cust = await _register_and_token(client, "buyer@test.com")

    # Hold the first two physical seats.
    hold = await client.post(f"/shows/{ctx['show_id']}/hold", headers=cust,
                             json={"seat_ids": ctx["seat_ids"][:2]})
    assert hold.status_code == 200
    show_seat_ids = hold.json()["show_seat_ids"]
    assert len(show_seat_ids) == 2

    # Those seats now read HELD.
    seats = (await client.get(f"/shows/{ctx['show_id']}/seats/")).json()
    held = [s for s in seats if s["status"] == "HELD"]
    assert len(held) == 2

    # Confirm the booking.
    booking = await client.post("/bookings/", headers=cust,
                                json={"show_id": ctx["show_id"], "show_seat_ids": show_seat_ids})
    assert booking.status_code == 200
    body = booking.json()
    assert body["status"] == "CONFIRMED"
    assert body["total_amount"] == "400.00"      # 200 * 2
    assert len(body["seats"]) == 2

    # Seats now read BOOKED.
    seats = (await client.get(f"/shows/{ctx['show_id']}/seats/")).json()
    assert len([s for s in seats if s["status"] == "BOOKED"]) == 2


async def test_cannot_hold_already_held_seats(client, admin_headers):
    ctx = await _setup_show(client, admin_headers)
    first = await _register_and_token(client, "first@test.com")
    second = await _register_and_token(client, "second@test.com")

    h1 = await client.post(f"/shows/{ctx['show_id']}/hold", headers=first,
                           json={"seat_ids": ctx["seat_ids"][:2]})
    assert h1.status_code == 200

    # A different user tries to grab an overlapping seat -> conflict.
    h2 = await client.post(f"/shows/{ctx['show_id']}/hold", headers=second,
                           json={"seat_ids": [ctx["seat_ids"][1]]})
    assert h2.status_code == 409


async def test_cancel_restores_seats(client, admin_headers):
    ctx = await _setup_show(client, admin_headers)
    cust = await _register_and_token(client, "canceller@test.com")

    hold = await client.post(f"/shows/{ctx['show_id']}/hold", headers=cust,
                             json={"seat_ids": ctx["seat_ids"][:2]})
    show_seat_ids = hold.json()["show_seat_ids"]
    booking = (await client.post("/bookings/", headers=cust,
                                 json={"show_id": ctx["show_id"],
                                       "show_seat_ids": show_seat_ids})).json()

    cancel = await client.post(f"/bookings/{booking['id']}/cancel", headers=cust)
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "CANCELLED"

    # All seats are AVAILABLE again.
    seats = (await client.get(f"/shows/{ctx['show_id']}/seats/")).json()
    assert all(s["status"] == "AVAILABLE" for s in seats)


async def test_cannot_book_someone_elses_seats_after_expiry_logic(client, admin_headers):
    """A booking referencing seats that were never held must be rejected."""
    ctx = await _setup_show(client, admin_headers)
    cust = await _register_and_token(client, "sneaky@test.com")

    # Grab the ShowSeat ids without holding them.
    seats = (await client.get(f"/shows/{ctx['show_id']}/seats/")).json()
    unhelded_ids = [s["id"] for s in seats[:2]]

    resp = await client.post("/bookings/", headers=cust,
                             json={"show_id": ctx["show_id"], "show_seat_ids": unhelded_ids})
    assert resp.status_code == 409


async def test_booking_requires_auth(client, admin_headers):
    ctx = await _setup_show(client, admin_headers)
    resp = await client.post("/bookings/",
                             json={"show_id": ctx["show_id"], "show_seat_ids": [1]})
    assert resp.status_code == 401
