"""Classification orchestration, private image storage, and RAG handoff."""
import os
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from ai_engine.classification.class_mapping import CLASS_LABELS, category_for
from ai_engine.classification.config import MODEL_VERSION
from app.models.classification import WasteClassification
from app.models.waste import WasteCategory

def confidence_label(score: float) -> str:
    return "High" if score >= 0.75 else "Moderate"

def map_category(db: Session, label: str):
    name = category_for(label)
    if name == "Requires manual review":
        return name, None
    row = db.query(WasteCategory).filter(WasteCategory.category_name == name).first()
    if row is None:
        raise RuntimeError(f"Waste category '{name}' is not seeded in the database.")
    return name, row

def save_private_image(data: bytes, image_format: str) -> str:
    root = Path(os.getenv("WASTE_UPLOAD_DIR", Path(__file__).resolve().parents[3] / ".private_uploads" / "classification")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    extension = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}[image_format]
    name = f"{uuid.uuid4().hex}{extension}"
    target = (root / name).resolve()
    if target.parent != root:
        raise ValueError("Unsafe upload path.")
    target.write_bytes(data)
    return target.relative_to(root.parent).as_posix()

def create_history(db: Session, user_id: int, image_path: str, result: dict, location: Optional[str]):
    label = result.get("predicted_class")
    category_name, category = map_category(db, label) if label else (None, None)
    row = WasteClassification(
        user_id=user_id, image_path=image_path, predicted_class=label,
        waste_category_id=category.id if category else None,
        confidence_score=result["confidence_score"], confidence_label=confidence_label(result["confidence_score"]),
        model_version=result.get("model_version", MODEL_VERSION),
        requires_confirmation=result["status"] == "uncertain" or label in ("Sanitary Products", "Battery / E-Waste", "Other / Unknown"),
        location=location,
    )
    db.add(row); db.commit(); db.refresh(row)
    return row, category_name

def owned_prediction(db: Session, prediction_id: int, user_id: int):
    return db.query(WasteClassification).options(joinedload(WasteClassification.waste_category)).filter(
        WasteClassification.id == prediction_id, WasteClassification.user_id == user_id
    ).first()

def guidance_for(label: str, category: str, location: Optional[str]):
    """Invoke the existing hybrid FAISS/BM25/reranker/Groq pipeline and citation validator."""
    from app.schemas.assistant import AssistantChatRequest
    from app.api.routes.assistant import get_rag_service
    question = (f"Predicted item class: {label}. Waste-management category: {category}. "
                f"How should this {label} waste item be prepared, segregated, and disposed of "
                "according to applicable verified guidance? Do not suggest unverified facilities.")
    return get_rag_service().answer(AssistantChatRequest(question=question, location=location))

def history_item(row: WasteClassification):
    return {"id": row.id, "predicted_class": row.predicted_class,
            "confirmed_class": row.confirmed_class,
            "waste_category": row.waste_category.category_name if row.waste_category else None,
            "confidence_score": row.confidence_score, "confidence_label": row.confidence_label,
            "model_version": row.model_version, "requires_confirmation": row.requires_confirmation,
            "location": row.location, "created_at": row.created_at}
