"""Stable model labels and configurable waste stream mapping."""
import os

CLASS_LABELS = [
    "Battery / E-Waste", "Glass", "Metal", "Organic / Food", "Other / Unknown",
    "Paper / Cardboard", "Plastic", "Sanitary Products",
]

# Folder names avoid separators in display labels, especially on Windows.
DATASET_CLASS_NAMES = {
    "Battery / E-Waste": "Battery_E-Waste",
    "Organic / Food": "Organic_Food",
    "Other / Unknown": "Other_Unknown",
    "Paper / Cardboard": "Paper_Cardboard",
}
DATASET_CLASS_DIRS = [DATASET_CLASS_NAMES.get(label, label) for label in CLASS_LABELS]

# Explicit source-folder aliases. TrashNet's paper/cardboard classes are merged;
# its untyped "trash" class maps only to the residual manual-review class.
SOURCE_LABEL_MAPPING = {
    "plastic": "Plastic",
    "paper": "Paper / Cardboard",
    "cardboard": "Paper / Cardboard",
    "metal": "Metal",
    "glass": "Glass",
    "trash": "Other / Unknown",
    "organic_food": "Organic / Food",
    "paper_cardboard": "Paper / Cardboard",
    "sanitary_products": "Sanitary Products",
    "battery_e_waste": "Battery / E-Waste",
    "other_unknown": "Other / Unknown",
}

def canonical_label_for_source(source_label: str):
    """Map a reviewed source class folder to one of the canonical model labels."""
    normalized = source_label.strip().casefold().replace(" ", "_").replace("-", "_")
    return SOURCE_LABEL_MAPPING.get(normalized)

DEFAULT_CATEGORY_MAPPING = {
    "Plastic": "Dry waste",
    "Paper / Cardboard": "Dry waste",
    "Metal": "Dry waste",
    "Glass": "Dry waste",
    "Organic / Food": "Wet waste",
    "Sanitary Products": "Sanitary waste",
    "Battery / E-Waste": "Special-care waste",
    "Other / Unknown": "Requires manual review",
}

def category_for(label: str) -> str:
    """Allow deployment-specific overrides using WASTE_CLASS_MAPPING JSON."""
    import json
    mapping = dict(DEFAULT_CATEGORY_MAPPING)
    raw = os.getenv("WASTE_CLASS_MAPPING")
    if raw:
        mapping.update(json.loads(raw))
    return mapping[label]
