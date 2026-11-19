"""
Test waste management endpoints (/api/waste)
"""


def test_get_categories(client):
    response = client.get("/api/waste/categories")
    assert response.status_code == 200
    categories = response.json()
    assert len(categories) == 4

    names = [c["name"] for c in categories]
    assert "Wet waste" in names
    assert "Dry waste" in names
    assert "Sanitary waste" in names
    assert "Special-care waste" in names

    for cat in categories:
        assert "description" in cat
        assert "color_code" in cat
        assert "examples" in cat
        assert len(cat["examples"]) > 0


def test_create_and_read_waste_report(client):
    report_data = {
        "title": "Discarded cardboard packaging",
        "category": "Dry waste",
        "description": "Clean packaging boxes piled outside building 4",
        "location": "North courtyard",
        "estimated_weight_kg": "12.5",
    }

    create_res = client.post("/api/waste/reports", json=report_data)
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["title"] == report_data["title"]
    assert created["category"] == "Dry waste"
    assert created["status"] == "reported"
    report_id = created["id"]

    read_res = client.get(f"/api/waste/reports/{report_id}")
    assert read_res.status_code == 200
    assert read_res.json()["id"] == report_id

    list_res = client.get("/api/waste/reports")
    assert list_res.status_code == 200
    ids = [r["id"] for r in list_res.json()]
    assert report_id in ids

    filtered = client.get("/api/waste/reports", params={"category": "Dry waste", "status": "reported"})
    assert filtered.status_code == 200
    assert any(r["id"] == report_id for r in filtered.json())


def test_create_report_invalid_category(client):
    bad_data = {
        "title": "Unknown substance",
        "category": "CompletelyInvalidCategoryX99",
        "description": "Mysterious pile",
    }
    response = client.post("/api/waste/reports", json=bad_data)
    assert response.status_code == 400
    assert "invalid waste category" in response.json()["detail"].lower()


def test_get_nonexistent_report(client):
    response = client.get("/api/waste/reports/999999")
    assert response.status_code == 404
