"""
Test collection pickup endpoints (/api/collection)
"""

def register(client, email):
    client.post("/api/auth/register", json={"email": email, "password": "Password123!"})
    token = client.post("/api/auth/login", json={"email": email, "password": "Password123!"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_create_collection_request_success(client):
    client.post("/api/auth/register", json={"email": "collection.create@example.com", "password": "Password123!"})
    token = client.post("/api/auth/login", json={"email": "collection.create@example.com", "password": "Password123!"}).json()["access_token"]
    payload = {
        "full_name": "Eleanor Vance",
        "email": "eleanor@example.org",
        "phone": "+1 555-234-5678",
        "category": "Electronic Scrap",
        "weight_tier": "Medium (10 – 50 kg)",
        "pickup_address": "42 Greenview Terrace, Building B, North Sector",
        "preferred_date": "2026-12-20",
        "time_slot": "Morning (08:00 – 12:00)",
        "special_instructions": "Gate code #4412"
    }

    response = client.post("/api/collection/requests", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 201
    data = response.json()
    assert data["full_name"] == payload["full_name"]
    assert data["category"] == "Special-care waste"
    assert data["status"] == "pending"
    req_id = data["id"]

    # Verify retrieval
    get_res = client.get(f"/api/collection/requests/{req_id}")
    assert get_res.status_code == 401


def test_collection_request_details_are_owner_scoped(client):
    client.post(
        "/api/auth/register",
        json={"email": "collection.owner@example.com", "password": "Password123!"},
    )
    client.post(
        "/api/auth/register",
        json={"email": "collection.other@example.com", "password": "Password123!"},
    )
    owner_token = client.post(
        "/api/auth/login",
        json={"email": "collection.owner@example.com", "password": "Password123!"},
    ).json()["access_token"]
    other_token = client.post(
        "/api/auth/login",
        json={"email": "collection.other@example.com", "password": "Password123!"},
    ).json()["access_token"]

    created = client.post(
        "/api/collection/requests",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "full_name": "Collection Owner",
            "email": "collection.owner@example.com",
            "phone": "+1 555-0101",
            "category": "Dry waste",
            "pickup_address": "10 Private Address Road",
        "preferred_date": "2026-12-10",
        },
    )
    assert created.status_code == 201
    request_path = f"/api/collection/requests/{created.json()['id']}"

    owner_read = client.get(request_path, headers={"Authorization": f"Bearer {owner_token}"})
    assert owner_read.status_code == 200
    assert owner_read.json()["email"] == "collection.owner@example.com"

    other_read = client.get(request_path, headers={"Authorization": f"Bearer {other_token}"})
    assert other_read.status_code == 404


def test_invalid_optional_bearer_token_is_rejected(client):
    response = client.post(
        "/api/collection/requests",
        headers={"Authorization": "Bearer invalid.token.value"},
        json={
            "full_name": "Collection Owner",
            "email": "collection.invalid-token@example.com",
            "phone": "+1 555-0101",
            "category": "Dry waste",
            "pickup_address": "10 Private Address Road",
            "preferred_date": "2026-12-10",
        },
    )
    assert response.status_code == 401


def test_collection_request_invalid_email(client):
    headers = register(client, "invalid.email.owner@example.com")
    payload = {
        "full_name": "Test User",
        "email": "not-an-email",
        "phone": "+1 555-123-4567",
        "category": "Dry waste",
        "pickup_address": "123 Long Street Name Here",
        "preferred_date": "2026-12-20"
    }
    response = client.post("/api/collection/requests", json=payload, headers=headers)
    assert response.status_code == 422


def test_collection_request_short_address(client):
    headers = register(client, "short.address.owner@example.com")
    payload = {
        "full_name": "Test User",
        "email": "user@example.com",
        "phone": "+1 555-123-4567",
        "category": "Dry waste",
        "pickup_address": "TooShort",  # < 10 chars
        "preferred_date": "2026-12-20"
    }
    response = client.post("/api/collection/requests", json=payload, headers=headers)
    assert response.status_code == 422


def test_get_nonexistent_collection_request(client):
    client.post(
        "/api/auth/register",
        json={"email": "collection.missing@example.com", "password": "Password123!"},
    )
    token = client.post(
        "/api/auth/login",
        json={"email": "collection.missing@example.com", "password": "Password123!"},
    ).json()["access_token"]
    response = client.get(
        "/api/collection/requests/999999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
