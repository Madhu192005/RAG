"""
Test recycling centers endpoints (/api/centers)
Centers are not seeded with invented facilities. Tests create records as admin.
"""

from app.models.role import Role
from app.models.user import User


def _promote_admin(db_session, email: str):
    admin_role = db_session.query(Role).filter(Role.role_name == "admin").first()
    user = db_session.query(User).filter(User.email == email).first()
    user.role_id = admin_role.id
    db_session.commit()


def _admin_headers(client, db_session, email="admin.centers@example.com"):
    client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "full_name": "Admin User"},
    )
    _promote_admin(db_session, email)
    token = client.post(
        "/api/auth/login",
        json={"email": email, "password": "Password123!"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_sample_centers(client, headers):
    payloads = [
        {
            "center_name": "Test Greenfield Drop-Off",
            "address": "100 Test Parkway",
            "city": "Greenfield",
            "state": "Test State",
            "postal_code": "00001",
            "phone": "+1 555-0100",
            "operating_hours": "Mon – Fri: 09:00 – 17:00",
            "verification_status": "verified",
            "accepted_categories": ["Dry waste", "Wet waste"],
        },
        {
            "center_name": "Test Riverside Organics Yard",
            "address": "200 Riverside Lane",
            "city": "Riverside",
            "state": "Test State",
            "postal_code": "00002",
            "phone": "+1 555-0101",
            "operating_hours": "Daily: 08:00 – 16:00",
            "verification_status": "verified",
            "accepted_categories": ["Wet waste"],
        },
    ]
    created = []
    for payload in payloads:
        response = client.post("/api/centers", json=payload, headers=headers)
        assert response.status_code == 201
        created.append(response.json())
    return created


def test_create_center_requires_admin(client):
    response = client.post(
        "/api/centers",
        json={
            "center_name": "Unauthorized Center",
            "address": "1 Example Street",
            "city": "Greenfield",
            "accepted_categories": ["Dry waste"],
        },
    )
    assert response.status_code == 401


def test_list_and_filter_recycling_centers(client, db_session):
    headers = _admin_headers(client, db_session)
    created = _create_sample_centers(client, headers)

    response = client.get("/api/centers")
    assert response.status_code == 200
    centers = response.json()
    assert len(centers) >= 2
    assert all(c["is_demo_data"] is False for c in centers)

    riverside = client.get("/api/centers", params={"location": "Riverside"})
    assert riverside.status_code == 200
    for c in riverside.json():
        blob = f"{c['city']} {c['address']} {c['name']}".lower()
        assert "riverside" in blob

    wet = client.get("/api/centers", params={"category": "Wet waste"})
    assert wet.status_code == 200
    assert len(wet.json()) > 0
    for c in wet.json():
        assert any("wet" in cat.lower() for cat in c["accepted_categories"])

    detail = client.get(f"/api/centers/{created[0]['id']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == created[0]["id"]


def test_get_nonexistent_center(client):
    response = client.get("/api/centers/99999")
    assert response.status_code == 404
