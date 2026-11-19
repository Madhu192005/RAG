"""Authenticated waste image classification and user-owned history."""
import io
import logging
from functools import lru_cache
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from ai_engine.classification.class_mapping import CLASS_LABELS, category_for
from ai_engine.classification.config import MAX_UPLOAD_BYTES, MODEL_VERSION
from ai_engine.classification.inference import ModelUnavailable, WasteClassifier
from ai_engine.classification.preprocessing import InvalidImageError, decode_image
from app.api.deps import get_current_user
from app.database.connection import get_db
from app.models.classification import WasteClassification
from app.models.user import User
from app.schemas.classification import ClassificationConfirmation, ClassificationConfirmationResponse, ClassificationHistoryItem
from app.services.classification_service import (
    confidence_label, create_history, guidance_for, history_item, map_category,
    owned_prediction, save_private_image,
)

router = APIRouter(prefix="/classification", tags=["Waste Classification"])
logger = logging.getLogger("wastewise_ai.classification")

@lru_cache(maxsize=1)
def get_classifier():
    return WasteClassifier()

@router.get("/classes")
def supported_classes():
    return {"classes": [{"class_name": label, "waste_category": category_for(label),
                         "requires_confirmation": label in ("Sanitary Products", "Battery / E-Waste", "Other / Unknown")}
                        for label in CLASS_LABELS], "model_version": MODEL_VERSION}

@router.post("/predict")
async def predict(file: UploadFile = File(...), location: Optional[str] = Form(None),
                  user_confirmation: Optional[str] = Form(None),
                  db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds the maximum upload size.")
    try:
        decode_image(content)
        from PIL import Image
        image_format = Image.open(io.BytesIO(content)).format
    except InvalidImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Image classification dependencies are not installed.") from exc
    if location and len(location) > 200:
        raise HTTPException(status_code=422, detail="Location must be at most 200 characters.")
    if user_confirmation is not None and user_confirmation not in CLASS_LABELS:
        raise HTTPException(status_code=422, detail="Unsupported confirmed class.")
    try:
        result = get_classifier().predict(content)
    except ModelUnavailable as exc:
        logger.error("Waste classifier unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="The waste classifier is not available until a compatible trained checkpoint is installed.") from exc
    except InvalidImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Waste classifier inference failed")
        raise HTTPException(status_code=503, detail="Image classification failed. Please try again.") from exc

    private_ref = save_private_image(content, image_format)
    history, category_name = create_history(db, current_user.id, private_ref, result, location)
    if result["status"] == "uncertain":
        return {**result, "classification_id": history.id, "requires_confirmation": True,
                "confidence_label": confidence_label(result["confidence_score"])}

    label = user_confirmation or result["predicted_class"]
    category_name, _ = map_category(db, label)
    if user_confirmation:
        _, confirmed_category = map_category(db, user_confirmation)
        history.confirmed_class = user_confirmation
        history.waste_category_id = confirmed_category.id if confirmed_category else None
        history.requires_confirmation = user_confirmation == "Other / Unknown"
        db.commit()
    sensitive = label in ("Sanitary Products", "Battery / E-Waste", "Other / Unknown")
    response = {"status": "success", "classification_id": history.id,
                "predicted_class": result["predicted_class"], "waste_category": category_name,
                "confidence_score": result["confidence_score"],
                "confidence_label": confidence_label(result["confidence_score"]),
                "top_predictions": result["top_predictions"],
                "requires_confirmation": label == "Other / Unknown" or (sensitive and not user_confirmation),
                "model_version": result["model_version"], "guidance": None}
    if label != "Other / Unknown" and (not sensitive or user_confirmation):
        try:
            response["guidance"] = guidance_for(label, category_name, location).model_dump()
        except Exception:
            logger.exception("Grounded disposal guidance unavailable")
            response["guidance_error"] = "Verified disposal guidance is temporarily unavailable."
    return response

@router.get("/history", response_model=list[ClassificationHistoryItem])
def classification_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = db.query(WasteClassification).options(joinedload(WasteClassification.waste_category)).filter(
        WasteClassification.user_id == current_user.id).order_by(WasteClassification.created_at.desc()).limit(100).all()
    return [history_item(row) for row in rows]

@router.get("/history/{prediction_id}", response_model=ClassificationHistoryItem)
def classification_history_item(prediction_id: int, db: Session = Depends(get_db),
                                current_user: User = Depends(get_current_user)):
    row = owned_prediction(db, prediction_id, current_user.id)
    if row is None: raise HTTPException(status_code=404, detail="Classification not found.")
    return history_item(row)

@router.post("/confirm", response_model=ClassificationConfirmationResponse)
def confirm_classification(payload: ClassificationConfirmation, db: Session = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    if payload.confirmed_class not in CLASS_LABELS:
        raise HTTPException(status_code=422, detail="Unsupported confirmed class.")
    row = owned_prediction(db, payload.prediction_id, current_user.id)
    if row is None: raise HTTPException(status_code=404, detail="Classification not found.")
    category_name, category = map_category(db, payload.confirmed_class)
    row.confirmed_class = payload.confirmed_class
    row.waste_category_id = category.id if category else None
    row.requires_confirmation = payload.confirmed_class == "Other / Unknown"
    db.commit()
    guidance = None
    if category and payload.confirmed_class != "Other / Unknown":
        try: guidance = guidance_for(payload.confirmed_class, category_name, row.location).model_dump()
        except Exception:
            logger.exception("Grounded disposal guidance unavailable after confirmation")
    return {"status": "success", "prediction_id": row.id, "confirmed_class": payload.confirmed_class,
            "waste_category": category_name, "guidance": guidance}
