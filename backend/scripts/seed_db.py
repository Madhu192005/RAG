"""
Seed roles and waste categories into wastewise_db.

Usage (from the backend directory, with the virtual environment active):

    python scripts/seed_db.py
"""

import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.database.connection import SessionLocal, check_database_connection  # noqa: E402
from app.services.seed_service import seed_reference_data  # noqa: E402


def main() -> int:
    if not check_database_connection():
        print("ERROR: Database connection failed. Check .env and that MySQL is running.")
        return 1

    db = SessionLocal()
    try:
        seed_reference_data(db)
        print("Seed completed: roles (admin, citizen, collector) and waste categories are present.")
        return 0
    except Exception as exc:
        print(f"ERROR: Seeding failed: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
