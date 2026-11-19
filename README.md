# WasteWise AI

WasteWise AI is a FastAPI and vanilla JavaScript waste management application with a SQLAlchemy/MySQL data layer, hybrid RAG assistant, and modular classification and collection features.

## Step 8: Smart recycling and collection

The center finder searches verified database records and only matches explicit accepted stream/material rows. It supports city/postal search, user-triggered nearby search, Leaflet/OpenStreetMap display for centers with stored coordinates, and recommendations linked to owned classifications. Collection requests are authenticated, user-scoped, and move through a staff-managed lifecycle with in-app notifications and audit records. Admin dashboard lifecycle totals come from database queries.

Apply migrations from `backend/` with `alembic upgrade head`, then follow [Step 8 architecture, API, test, and limitation notes](docs/SMART_RECYCLING_AND_COLLECTION.md). No recycling center records are seeded or invented; administrators must curate and verify real records. A trained Step 7 checkpoint is also required before image inference is available.
