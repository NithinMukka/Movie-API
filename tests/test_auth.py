"""Auth: registration, login, token-protected and admin-only access."""


async def test_register_success(client):
    resp = await client.post("/auth/register", json={
        "name": "Alice", "email": "alice@test.com", "password": "pw123456",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "alice@test.com"
    assert body["role"] == "customer"          # always forced to customer
    assert "password" not in body
    assert "password_hash" not in body


async def test_register_rejects_malformed_email(client):
    resp = await client.post("/auth/register", json={
        "name": "Bad", "email": "not-an-email", "password": "pw123456",
    })
    assert resp.status_code == 422  # Pydantic validation error


async def test_register_rejects_short_password(client):
    resp = await client.post("/auth/register", json={
        "name": "Bad", "email": "shortpw@test.com", "password": "abc",
    })
    assert resp.status_code == 422


async def test_register_duplicate_email(client):
    payload = {"name": "Bob", "email": "bob@test.com", "password": "pw123456"}
    first = await client.post("/auth/register", json=payload)
    assert first.status_code == 200
    second = await client.post("/auth/register", json=payload)
    assert second.status_code == 400


async def test_login_success_and_me(client):
    await client.post("/auth/register", json={
        "name": "Carol", "email": "carol@test.com", "password": "pw123456",
    })
    # OAuth2 form: username field carries the email.
    login = await client.post("/auth/login", data={
        "username": "carol@test.com", "password": "pw123456",
    })
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "carol@test.com"


async def test_login_wrong_password(client):
    await client.post("/auth/register", json={
        "name": "Dave", "email": "dave@test.com", "password": "pw123456",
    })
    login = await client.post("/auth/login", data={
        "username": "dave@test.com", "password": "wrongpass",
    })
    assert login.status_code == 401


async def test_protected_route_requires_token(client):
    assert (await client.get("/users/me")).status_code == 401


async def test_admin_only_route_blocks_customer(client, customer_headers):
    # A customer must not be able to create movies.
    resp = await client.post("/movies/", headers=customer_headers, json={
        "title": "X", "description": "Y", "duration_mins": 120,
    })
    assert resp.status_code == 403


async def test_admin_can_create_movie(client, admin_headers):
    resp = await client.post("/movies/", headers=admin_headers, json={
        "title": "Dune", "description": "Sci-fi", "duration_mins": 155,
    })
    assert resp.status_code == 200
    assert resp.json()["title"] == "Dune"
