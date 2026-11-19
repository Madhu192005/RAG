"""
Test authentication endpoints (/api/auth)
"""

def test_register_user_success(client):
    payload = {
        "email": "ecocitizen@example.com",
        "password": "SecurePassword123!",
        "full_name": "Eco Citizen",
        "phone": "+1 (555) 987-6543"
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "ecocitizen@example.com"
    assert data["full_name"] == "Eco Citizen"
    assert "id" in data
    assert "hashed_password" not in data  # Never expose hashed passwords


def test_register_duplicate_email(client):
    payload = {
        "email": "unique@example.com",
        "password": "Password123!",
        "full_name": "User One"
    }
    res1 = client.post("/api/auth/register", json=payload)
    assert res1.status_code == 201

    # Second attempt with same email
    res2 = client.post("/api/auth/register", json=payload)
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"].lower()


def test_register_short_password(client):
    payload = {
        "email": "shortpwd@example.com",
        "password": "short"  # < 8 chars
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 422  # Pydantic validation error


def test_login_success(client):
    # Register user first
    client.post("/api/auth/register", json={
        "email": "loginuser@example.com",
        "password": "MySecretPassword123!"
    })

    # Log in
    response = client.post("/api/auth/login", json={
        "email": "loginuser@example.com",
        "password": "MySecretPassword123!"
    })
    assert response.status_code == 200
    token = response.json()
    assert "access_token" in token
    assert token["token_type"] == "bearer"
    assert token["expires_in"] > 0


def test_login_invalid_password(client):
    client.post("/api/auth/register", json={
        "email": "badpwd@example.com",
        "password": "CorrectPassword123!"
    })

    response = client.post("/api/auth/login", json={
        "email": "badpwd@example.com",
        "password": "WrongPassword!"
    })
    assert response.status_code == 401
    assert "incorrect email or password" in response.json()["detail"].lower()


def test_login_nonexistent_email(client):
    response = client.post("/api/auth/login", json={
        "email": "ghost@example.com",
        "password": "SomePassword123!"
    })
    assert response.status_code == 401


def test_auth_me_with_valid_token(client):
    client.post("/api/auth/register", json={
        "email": "metest@example.com",
        "password": "ValidPassword123!",
        "full_name": "Me Test"
    })

    login_res = client.post("/api/auth/login", json={
        "email": "metest@example.com",
        "password": "ValidPassword123!"
    })
    token = login_res.json()["access_token"]

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "metest@example.com"
    assert response.json()["full_name"] == "Me Test"


def test_auth_me_unauthorized(client):
    # No header
    res1 = client.get("/api/auth/me")
    assert res1.status_code == 401

    # Fake token
    res2 = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.fake.token"})
    assert res2.status_code == 401
