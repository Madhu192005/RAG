"""Focused checks for classification mapping, image validation, ownership, and API states."""
import io

import pytest
from PIL import Image

from ai_engine.classification.class_mapping import CLASS_LABELS, DEFAULT_CATEGORY_MAPPING, canonical_label_for_source
from ai_engine.classification.inference import ModelUnavailable, WasteClassifier
from ai_engine.classification.preprocessing import InvalidImageError, decode_image
from app.models.classification import WasteClassification
from app.models.role import Role
from app.models.user import User
from app.services.classification_service import owned_prediction
from app.schemas.assistant import AssistantChatResponse

def png_bytes():
    stream = io.BytesIO(); Image.new("RGB", (64, 64), "white").save(stream, format="PNG"); return stream.getvalue()

def test_all_eight_class_mappings_are_present():
    assert len(CLASS_LABELS) == 8
    assert set(DEFAULT_CATEGORY_MAPPING) == set(CLASS_LABELS)
    assert DEFAULT_CATEGORY_MAPPING["Metal"] == "Dry waste"
    assert DEFAULT_CATEGORY_MAPPING["Battery / E-Waste"] == "Special-care waste"
    assert canonical_label_for_source("cardboard") == "Paper / Cardboard"
    assert canonical_label_for_source("paper") == "Paper / Cardboard"
    assert canonical_label_for_source("trash") == "Other / Unknown"

def test_valid_image_decodes_to_rgb():
    assert decode_image(png_bytes()).mode == "RGB"

@pytest.mark.parametrize("payload", [b"", b"not an image", b"\x00\x01\x02"])
def test_corrupt_images_are_rejected(payload):
    with pytest.raises(InvalidImageError): decode_image(payload)

def test_missing_checkpoint_is_explicit(tmp_path):
    classifier = WasteClassifier(tmp_path / "missing.pt")
    with pytest.raises(ModelUnavailable): classifier.load()

def test_classification_history_is_owner_scoped(db_session):
    role = db_session.query(Role).filter_by(role_name="citizen").first()
    first = User(email="vision-one@example.com", hashed_password="x", role_id=role.id)
    second = User(email="vision-two@example.com", hashed_password="x", role_id=role.id)
    db_session.add_all([first, second]); db_session.flush()
    item = WasteClassification(user_id=first.id, image_path="classification/private.png", predicted_class="Plastic",
                               confidence_score=.8, confidence_label="High", model_version="test", requires_confirmation=False)
    db_session.add(item); db_session.commit()
    assert owned_prediction(db_session, item.id, first.id) is not None
    assert owned_prediction(db_session, item.id, second.id) is None

def test_predict_endpoint_rejects_unauthenticated_upload(client):
    response = client.post("/api/classification/predict", files={"file": ("item.png", png_bytes(), "image/png")})
    assert response.status_code == 401

def test_predict_endpoint_rejects_corrupted_image(client, auth_headers):
    response = client.post("/api/classification/predict", headers=auth_headers,
                           files={"file": ("item.png", b"not really png", "image/png")})
    assert response.status_code == 400

def test_predict_endpoint_rejects_oversized_upload(client, auth_headers):
    from ai_engine.classification.config import MAX_UPLOAD_BYTES
    response = client.post("/api/classification/predict", headers=auth_headers,
                           files={"file": ("large.png", b"x" * (MAX_UPLOAD_BYTES + 1), "image/png")})
    assert response.status_code == 413

def test_predict_endpoint_reports_model_inference_error(client, auth_headers, monkeypatch):
    import app.api.routes.classification as route
    class BrokenClassifier:
        def predict(self, _data): raise RuntimeError("internal model detail")
    monkeypatch.setattr(route, "get_classifier", lambda: BrokenClassifier())
    response = client.post("/api/classification/predict", headers=auth_headers,
                           files={"file": ("item.png", png_bytes(), "image/png")})
    assert response.status_code == 503
    assert response.json()["detail"] == "Image classification failed. Please try again."

def test_predict_returns_top_three_and_grounded_guidance(client, auth_headers, monkeypatch, tmp_path):
    import app.api.routes.classification as route
    monkeypatch.setenv("WASTE_UPLOAD_DIR", str(tmp_path))
    class FakeClassifier:
        def predict(self, _data):
            return {"status": "success", "predicted_class": "Plastic", "confidence_score": .82,
                    "top_predictions": [{"class_name": "Plastic", "score": .82},
                                        {"class_name": "Paper / Cardboard", "score": .1},
                                        {"class_name": "Glass", "score": .04}], "model_version": "test"}
    guidance = AssistantChatResponse(answer="Rinse if locally accepted. [C1]", question="How?",
        confidence="Moderate evidence", sources=[{"title":"Local guide", "snippet":"Rinse if accepted.",
        "document_id":"doc", "chunk_id":"chunk", "citation_id":"C1"}], status="success")
    monkeypatch.setattr(route, "get_classifier", lambda: FakeClassifier())
    def fake_guidance(label, category, location):
        assert label == "Plastic" and category == "Dry waste" and location == "Chennai"
        return guidance
    monkeypatch.setattr(route, "guidance_for", fake_guidance)
    response = client.post("/api/classification/predict", headers=auth_headers,
                           files={"file": ("item.png", png_bytes(), "application/octet-stream")},
                           data={"location": "Chennai"})
    assert response.status_code == 200
    data = response.json()
    assert data["predicted_class"] == "Plastic"
    assert len(data["top_predictions"]) == 3
    assert data["guidance"]["sources"][0]["citation_id"] == "C1"
    assert data["waste_category"] == "Dry waste"

def test_uncertain_prediction_requires_manual_review(client, auth_headers, monkeypatch, tmp_path):
    import app.api.routes.classification as route
    monkeypatch.setenv("WASTE_UPLOAD_DIR", str(tmp_path))
    class UncertainClassifier:
        def predict(self, _data):
            return {"status": "uncertain", "message": "Please verify manually.", "prediction": None,
                    "confidence_score": .31, "top_predictions": []}
    monkeypatch.setattr(route, "get_classifier", lambda: UncertainClassifier())
    response = client.post("/api/classification/predict", headers=auth_headers,
                           files={"file": ("item.png", png_bytes(), "image/png")})
    assert response.status_code == 200
    assert response.json()["status"] == "uncertain"
    assert response.json()["prediction"] is None
    assert response.json()["requires_confirmation"] is True

def test_confirmation_and_history_remain_user_scoped(client, auth_headers, db_session, monkeypatch, tmp_path):
    import app.api.routes.classification as route
    monkeypatch.setenv("WASTE_UPLOAD_DIR", str(tmp_path))
    class UncertainClassifier:
        def predict(self, _data):
            return {"status": "uncertain", "message": "Verify manually.", "prediction": None,
                    "confidence_score": .4, "top_predictions": []}
    monkeypatch.setattr(route, "get_classifier", lambda: UncertainClassifier())
    created = client.post("/api/classification/predict", headers=auth_headers,
        files={"file": ("item.png", png_bytes(), "image/png")})
    prediction_id = created.json()["classification_id"]
    confirmed = client.post("/api/classification/confirm", headers=auth_headers,
        json={"prediction_id": prediction_id, "confirmed_class": "Plastic"})
    assert confirmed.status_code == 200 and confirmed.json()["waste_category"] == "Dry waste"
    assert client.get(f"/api/classification/history/{prediction_id}", headers=auth_headers).status_code == 200
    client.post("/api/auth/register", json={"email":"classification.other@example.com", "password":"Password123!"})
    token = client.post("/api/auth/login", json={"email":"classification.other@example.com", "password":"Password123!"}).json()["access_token"]
    assert client.get(f"/api/classification/history/{prediction_id}", headers={"Authorization":f"Bearer {token}"}).status_code == 404
