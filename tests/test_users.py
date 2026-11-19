"""
Test user profile endpoints (/api/users)
"""

def test_user_profile_workflow(client):
    # 1. Register & login
    client.post("/api/auth/register", json={
        "email": "profileuser@example.com",
        "password": "Password123!",
        "full_name": "Original Name"
    })
    token = client.post("/api/auth/login", json={
        "email": "profileuser@example.com",
        "password": "Password123!"
    }).json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get profile
    get_res = client.get("/api/users/profile", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["full_name"] == "Original Name"

    # 3. Update profile
    update_res = client.put(
        "/api/users/profile",
        headers=headers,
        json={
            "full_name": "Updated Name",
            "phone": "+1 555-4321",
            "address": "123 Eco Way"
        }
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["full_name"] == "Updated Name"
    assert updated["phone"] == "+1 555-4321"
    assert updated["address"] == "123 Eco Way"


def test_user_profile_unauthorized(client):
    res = client.get("/api/users/profile")
    assert res.status_code == 401
