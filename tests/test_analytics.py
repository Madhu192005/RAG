"""
Test analytics endpoints (/api/analytics)
Values must come from stored records, not hardcoded demo metrics.
"""

from datetime import datetime

import pytest

from app.models.collection import CollectionRecord, CollectionRequest
from app.models.waste import WasteCategory


def test_analytics_summary(client):
    client.post("/api/auth/register", json={"email": "analytics.request@example.com", "password": "Password123!"})
    token = client.post("/api/auth/login", json={"email": "analytics.request@example.com", "password": "Password123!"}).json()["access_token"]
    client.post(
        "/api/waste/reports",
        json={
            "title": "Analytics cardboard",
            "category": "Dry waste",
            "estimated_weight_kg": "10",
        },
    )
    client.post(
        "/api/collection/requests",
        json={
            "full_name": "Analytics User",
            "email": "analytics@example.com",
            "phone": "+1 555-000-1111",
            "category": "Dry waste",
            "pickup_address": "100 Analytics Avenue",
            "preferred_date": "2026-12-01",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    response = client.get("/api/analytics/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["is_demo_data"] is False
    assert data["total_waste_reports"] >= 1
    assert data["total_collection_requests"] >= 1
    assert isinstance(data["reports_by_category"], list)
    assert isinstance(data["collection_status_breakdown"], list)
    assert "total_waste_logged_kg" in data
    assert "pending_pickups_count" in data


def test_analytics_monthly(client):
    response = client.get("/api/analytics/monthly")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) == 12
    assert data["is_demo_data"] is False
    for pt in data["data"]:
        assert "month" in pt
        assert "collected_kg" in pt
        assert "diverted_kg" in pt


def test_analytics_categories(client):
    response = client.get("/api/analytics/categories")
    assert response.status_code == 200
    data = response.json()
    assert "categories" in data
    assert len(data["categories"]) == 4
    cat_names = [c["category"] for c in data["categories"]]
    assert "Dry waste" in cat_names
    assert "Wet waste" in cat_names
    assert "Sanitary waste" in cat_names
    assert "Special-care waste" in cat_names
    assert data["is_demo_data"] is False


def test_monthly_analytics_uses_recorded_quantities(client, db_session):
    month_index = datetime.utcnow().month - 1

    def monthly_point():
        response = client.get("/api/analytics/monthly")
        assert response.status_code == 200
        return response.json()["data"][month_index]

    before = monthly_point()
    category = db_session.query(WasteCategory).filter_by(category_name="Dry waste").one()
    request = CollectionRequest(
        category_id=category.id,
        full_name="Monthly Analytics",
        email="monthly.analytics@example.com",
        phone="+1 555-0102",
        category_label="Dry waste",
        pickup_address="20 Monthly Analytics Street",
        preferred_pickup_date="2026-12-10",
        status="completed",
    )
    db_session.add(request)
    db_session.flush()
    db_session.add(
        CollectionRecord(
            request_id=request.id,
            collected_quantity=3.25,
            quantity_unit="kg",
            collected_at=datetime.utcnow(),
        )
    )
    db_session.commit()

    after = monthly_point()
    assert after["collected_kg"] - before["collected_kg"] == pytest.approx(3.25)
    assert after["diverted_kg"] - before["diverted_kg"] == pytest.approx(3.25)
