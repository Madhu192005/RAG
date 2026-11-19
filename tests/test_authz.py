"""
Role-based authorization and collection status tests.
"""

from app.models.role import Role
from app.models.user import User


def _login(client, email, password="Password123!"):
    return client.post("/api/auth/login", json={"email": email, "password": password}).json()["access_token"]


def _promote(db_session, email, role_name):
    role = db_session.query(Role).filter(Role.role_name == role_name).first()
    user = db_session.query(User).filter(User.email == email).first()
    user.role_id = role.id
    db_session.commit()


def test_admin_can_list_users(client, db_session):
    client.post(
        "/api/auth/register",
        json={"email": "admin.users@example.com", "password": "Password123!", "full_name": "Admin"},
    )
    client.post(
        "/api/auth/register",
        json={"email": "plain.users@example.com", "password": "Password123!", "full_name": "Plain"},
    )
    _promote(db_session, "admin.users@example.com", "admin")

    citizen_token = _login(client, "plain.users@example.com")
    denied = client.get("/api/users", headers={"Authorization": f"Bearer {citizen_token}"})
    assert denied.status_code == 403

    admin_token = _login(client, "admin.users@example.com")
    allowed = client.get("/api/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert allowed.status_code == 200
    emails = [u["email"] for u in allowed.json()]
    assert "plain.users@example.com" in emails


def test_collection_status_update_authorization(client, db_session):
    client.post(
        "/api/auth/register",
        json={"email": "owner.col@example.com", "password": "Password123!"},
    )
    client.post(
        "/api/auth/register",
        json={"email": "collector.col@example.com", "password": "Password123!"},
    )
    client.post(
        "/api/auth/register",
        json={"email": "other.col@example.com", "password": "Password123!"},
    )
    _promote(db_session, "collector.col@example.com", "collector")

    owner_token = _login(client, "owner.col@example.com")
    created = client.post(
        "/api/collection/requests",
        json={
            "full_name": "Owner",
            "email": "owner.col@example.com",
            "phone": "+1 555-222-3333",
            "category": "Dry waste",
            "pickup_address": "500 Owner Street Name",
            "preferred_date": "2026-12-02",
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert created.status_code == 201
    request_id = created.json()["id"]

    other_token = _login(client, "other.col@example.com")
    forbidden = client.patch(
        f"/api/collection/requests/{request_id}/status",
        json={"status": "cancelled"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert forbidden.status_code == 404

    owner_cancel = client.patch(
        f"/api/collection/requests/{request_id}/status",
        json={"status": "in_progress"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert owner_cancel.status_code == 403

    collector_token = _login(client, "collector.col@example.com")
    unassigned = client.patch(
        f"/api/collection/requests/{request_id}/status",
        json={"status": "in_progress"},
        headers={"Authorization": f"Bearer {collector_token}"},
    )
    assert unassigned.status_code == 404


def test_notifications_are_user_scoped(client):
    client.post(
        "/api/auth/register",
        json={"email": "notify.user@example.com", "password": "Password123!"},
    )
    token = _login(client, "notify.user@example.com")
    response = client.get("/api/notifications", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1
