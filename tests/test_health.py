"""
Test health and root endpoints
"""


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == "WasteWise AI"
    assert data["step"] == "Step 8 – Smart Recycling Centers and Collection Management"
    assert "health" in data


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in {"healthy", "degraded"}
    assert data["service"] == "WasteWise AI Backend"
    assert "timestamp" in data
    assert "database" in data
    assert "ai_engine" in data
