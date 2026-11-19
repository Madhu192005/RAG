"""Step 8 center matching, collection lifecycle, privacy, and operations metrics."""
from datetime import date, timedelta

from app.models.classification import WasteClassification
from app.models.role import Role
from app.models.user import User


def register(client, email):
    client.post("/api/auth/register", json={"email": email, "password": "Password123!"})
    token = client.post("/api/auth/login", json={"email": email, "password": "Password123!"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def promote(db, email, role_name):
    user = db.query(User).filter_by(email=email).one()
    role = db.query(Role).filter_by(role_name=role_name).one()
    user.role_id = role.id
    db.commit()


def test_haversine_distance_is_in_kilometers():
    from app.services.center_service import haversine_distance_km
    assert 1.10 < haversine_distance_km(0, 0, 0, .01) < 1.12


def test_nearby_requires_explicit_material_acceptance(client, db_session):
    headers = register(client, "step8.center.admin@example.com")
    promote(db_session, "step8.center.admin@example.com", "admin")
    created = client.post("/api/recycling-centers", headers=headers, json={
        "center_name": "Step Eight Plastic Center", "address": "10 Verified Road", "city": "Pune",
        "verification_status": "verified", "latitude": 0.0, "longitude": 0.01,
        "accepted_waste_types": ["Plastic"],
    })
    assert created.status_code == 201
    nearby = client.get("/api/recycling-centers/nearby", params={
        "latitude": 0, "longitude": 0, "radius_km": 5, "waste_type": "Plastic"
    })
    assert nearby.status_code == 200
    matches = nearby.json()["matching_centers"]
    assert len(matches) == 1 and matches[0]["id"] == created.json()["id"]
    assert 1.1 < matches[0]["distance_km"] < 1.12
    # A material-specific record does not imply broad stream acceptance.
    broad = client.get("/api/recycling-centers", params={"category": "Dry waste"})
    assert created.json()["id"] not in [item["id"] for item in broad.json()]


def test_nearby_validates_coordinates_and_radius(client):
    invalid_coords = client.get("/api/recycling-centers/nearby", params={
        "latitude": 91, "longitude": 0, "radius_km": 5, "waste_type": "Plastic"
    })
    invalid_radius = client.get("/api/recycling-centers/nearby", params={
        "latitude": 0, "longitude": 0, "radius_km": 51, "waste_type": "Plastic"
    })
    assert invalid_coords.status_code == 422
    assert invalid_radius.status_code == 422


def test_classification_recommendation_requires_confirmation_and_ownership(client, db_session):
    owner_headers = register(client, "step8.class.owner@example.com")
    register(client, "step8.class.other@example.com")
    owner = db_session.query(User).filter_by(email="step8.class.owner@example.com").one()
    other_token = client.post("/api/auth/login", json={"email": "step8.class.other@example.com", "password": "Password123!"}).json()["access_token"]
    classification = WasteClassification(user_id=owner.id, image_path="classification/private.png",
        predicted_class="Plastic", confidence_score=.8, confidence_label="High", model_version="test",
        requires_confirmation=True)
    db_session.add(classification); db_session.commit()
    path = f"/api/recycling-centers/recommendations/{classification.id}"
    assert client.get(path, headers=owner_headers).status_code == 409
    other = client.get(path, headers={"Authorization": f"Bearer {other_token}"})
    assert other.status_code == 404
    classification.confirmed_class = "Plastic"
    classification.requires_confirmation = False
    db_session.commit()
    no_match = client.get(path, headers=owner_headers)
    assert no_match.status_code == 200 and no_match.json()["status"] == "no_matches"


def test_collection_from_classification_checks_confirmation_and_exact_center_acceptance(client, db_session):
    owner_headers = register(client, "step8.class.collection@example.com")
    admin_headers = register(client, "step8.class.centeradmin@example.com")
    promote(db_session, "step8.class.centeradmin@example.com", "admin")
    center = client.post("/api/centers", headers=admin_headers, json={
        "center_name": "Exact Plastic Acceptance", "address": "10 Material Road", "city": "Surat",
        "verification_status": "verified", "accepted_waste_types": ["Plastic"]
    }).json()
    owner = db_session.query(User).filter_by(email="step8.class.collection@example.com").one()
    classification = WasteClassification(user_id=owner.id, image_path="classification/owned.png",
        predicted_class="Plastic", confidence_score=.9, confidence_label="High", model_version="test",
        requires_confirmation=True)
    db_session.add(classification); db_session.commit()
    request = {"full_name": "Classification Owner", "email": "step8.class.collection@example.com",
        "phone": "5551234567", "waste_classification_id": classification.id,
        "recycling_center_id": center["id"], "pickup_address": "10 Collection Address Road",
        "requested_date": (date.today() + timedelta(days=5)).isoformat()}
    denied = client.post("/api/collections/requests", headers=owner_headers, json=request)
    assert denied.status_code == 409
    classification.confirmed_class = "Plastic"; classification.requires_confirmation = False
    db_session.commit()
    accepted = client.post("/api/collections/requests", headers=owner_headers, json=request)
    assert accepted.status_code == 201
    assert accepted.json()["waste_classification_id"] == classification.id
    assert accepted.json()["recycling_center_id"] == center["id"]


def test_admin_center_update_and_soft_deactivation(client, db_session):
    admin_headers = register(client, "step8.center.lifecycle.admin@example.com")
    promote(db_session, "step8.center.lifecycle.admin@example.com", "admin")
    created = client.post("/api/centers", headers=admin_headers, json={
        "center_name": "Pending Center Record", "address": "20 Review Street", "city": "Indore",
        "verification_status": "pending", "accepted_categories": ["Wet waste"]
    })
    center_id = created.json()["id"]
    assert client.get(f"/api/centers/{center_id}").status_code == 404
    verified = client.put(f"/api/centers/{center_id}", headers=admin_headers,
        json={"verification_status": "verified"})
    assert verified.status_code == 200
    assert client.get(f"/api/centers/{center_id}").status_code == 200
    deactivated = client.delete(f"/api/centers/{center_id}", headers=admin_headers)
    assert deactivated.status_code == 200 and deactivated.json()["is_active"] is False
    assert client.get(f"/api/centers/{center_id}").status_code == 404


def test_collection_lifecycle_owner_staff_and_notifications(client, db_session):
    owner_headers = register(client, "step8.lifecycle.owner@example.com")
    admin_headers = register(client, "step8.lifecycle.admin@example.com")
    register(client, "step8.lifecycle.collector@example.com")
    register(client, "step8.lifecycle.other@example.com")
    promote(db_session, "step8.lifecycle.admin@example.com", "admin")
    promote(db_session, "step8.lifecycle.collector@example.com", "collector")
    collector = db_session.query(User).filter_by(email="step8.lifecycle.collector@example.com").one()
    other_token = client.post("/api/auth/login", json={"email": "step8.lifecycle.other@example.com", "password": "Password123!"}).json()["access_token"]

    created = client.post("/api/collections/requests", headers=owner_headers, json={
        "full_name": "Private Owner", "email": "step8.lifecycle.owner@example.com", "phone": "5551234567",
        "category": "Dry waste", "pickup_address": "42 Private Address Road",
        "requested_date": (date.today() + timedelta(days=10)).isoformat(), "quantity": "4.25",
    })
    assert created.status_code == 201
    request_id = created.json()["id"]
    assert created.json()["status"] == "pending"
    assert client.get(f"/api/collections/requests/{request_id}", headers={"Authorization": f"Bearer {other_token}"}).status_code == 404

    approved = client.patch(f"/api/collections/requests/{request_id}/status", headers=admin_headers,
                            json={"status": "approved", "internal_notes": "Reviewed internally"})
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    assigned = client.patch(f"/api/collections/requests/{request_id}/assign", headers=admin_headers,
                            json={"assigned_staff_id": collector.id})
    assert assigned.status_code == 200 and assigned.json()["status"] == "assigned"
    assert client.get(f"/api/collections/requests/{request_id}/staff-details", headers=owner_headers).status_code == 404
    assert client.get(f"/api/collections/requests/{request_id}/staff-details", headers=admin_headers).json()["internal_notes"] == "Reviewed internally"

    admin_scheduled = client.patch(f"/api/collections/requests/{request_id}/status", headers=admin_headers, json={"status": "scheduled"})
    assert admin_scheduled.status_code == 200
    collector_token = client.post("/api/auth/login", json={"email": "step8.lifecycle.collector@example.com", "password": "Password123!"}).json()["access_token"]
    staff_headers = {"Authorization": f"Bearer {collector_token}"}
    assert client.patch(f"/api/collections/requests/{request_id}/status", headers=staff_headers, json={"status": "in_progress"}).status_code == 200
    completed = client.patch(f"/api/collections/requests/{request_id}/status", headers=staff_headers,
        json={"status": "completed", "collected_quantity": "3.5", "quantity_unit": "kg"})
    assert completed.status_code == 200 and completed.json()["status"] == "completed"
    detail = client.get(f"/api/collections/requests/{request_id}/staff-details", headers=staff_headers)
    assert detail.status_code == 200 and len(detail.json()["collection_records"]) == 1
    assert client.get("/api/collections/history", headers=owner_headers).json()[0]["id"] == request_id
    assert client.get("/api/notifications", headers=owner_headers).json()


def test_collection_cancel_and_invalid_status_transition(client):
    owner_headers = register(client, "step8.cancel.owner@example.com")
    payload = {"full_name": "Cancel Owner", "email": "step8.cancel.owner@example.com", "phone": "5551234567",
               "category": "Wet waste", "pickup_address": "10 Cancel Address Lane",
               "requested_date": (date.today() + timedelta(days=2)).isoformat()}
    created = client.post("/api/collections/requests", headers=owner_headers, json=payload)
    request_id = created.json()["id"]
    invalid = client.patch(f"/api/collections/requests/{request_id}/status", headers=owner_headers,
                           json={"status": "completed"})
    cancelled = client.patch(f"/api/collections/requests/{request_id}/cancel", headers=owner_headers)
    assert invalid.status_code == 403
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"


def test_collection_operations_dashboard_requires_admin(client, db_session):
    user_headers = register(client, "step8.dashboard.user@example.com")
    denied = client.get("/api/analytics/collection-operations", headers=user_headers)
    assert denied.status_code == 403
    admin_headers = register(client, "step8.dashboard.admin@example.com")
    promote(db_session, "step8.dashboard.admin@example.com", "admin")
    data = client.get("/api/analytics/collection-operations", headers=admin_headers)
    assert data.status_code == 200 and data.json()["is_demo_data"] is False
    assert "pending" in data.json()["collection_requests"]
