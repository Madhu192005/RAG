"""
WasteWise AI – Reference Data Seeding
--------------------------------------
Idempotent inserts for roles and waste categories only.
Does not invent recycling center facilities.
"""

import logging

from sqlalchemy.orm import Session

from app.models.role import Role
from app.models.waste import WasteCategory

logger = logging.getLogger("wastewise_ai.seed")

INITIAL_ROLES = [
    ("admin", "Platform administrator with full operational access."),
    ("citizen", "Registered resident who can report waste and request collection."),
    ("collector", "Field collector who updates pickup and collection records."),
]

INITIAL_CATEGORIES = [
    ("Wet waste", "Biodegradable organic waste including kitchen and food residuals."),
    ("Dry waste", "Non-biodegradable recyclable or recoverable clean materials."),
    ("Sanitary waste", "Personal hygiene items requiring safe encapsulation."),
    ("Special-care waste", "Hazardous, chemical, electrical, or toxic domestic materials."),
]


def seed_reference_data(db: Session) -> None:
    """Insert roles and waste categories when they are missing."""
    existing_roles = {row.role_name for row in db.query(Role.role_name).all()}
    for name, description in INITIAL_ROLES:
        if name not in existing_roles:
            db.add(Role(role_name=name, description=description))

    existing_categories = {row.category_name for row in db.query(WasteCategory.category_name).all()}
    for name, description in INITIAL_CATEGORIES:
        if name not in existing_categories:
            db.add(WasteCategory(category_name=name, description=description))

    db.commit()
    logger.info("Reference data verified (roles and waste categories).")


def get_role_by_name(db: Session, role_name: str) -> Role:
    role = db.query(Role).filter(Role.role_name == role_name).first()
    if role is None:
        raise RuntimeError(
            f"Required role '{role_name}' is missing. Run the seed script after migrations."
        )
    return role


def get_category_by_name(db: Session, category_name: str) -> WasteCategory:
    category = db.query(WasteCategory).filter(WasteCategory.category_name == category_name).first()
    if category is None:
        raise RuntimeError(
            f"Required waste category '{category_name}' is missing. Run the seed script after migrations."
        )
    return category
