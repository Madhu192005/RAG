# Step 8: Smart recycling and collection

## Architecture

This extends the existing center, accepted-waste, collection request/record, notification, and audit-log modules. MySQL is the source of truth for centers and requests. A center is publicly eligible only when it is active and verified. Its accepted categories and material labels are explicit rows in `accepted_waste_types`; the recommendation service does not infer acceptance from the name or type of a center. The image classifier supplies a label, the MySQL directory matches that label, and the collection service manages pickup requests. The RAG service remains responsible only for cited disposal guidance; it does not generate center names or availability.

## Database and migration

Apply the new chain after the Step 7 migration from `backend/`:

```powershell
alembic upgrade head
```

Migration `20261118_0005` adds center description, country, email, center type, active state, and update timestamp; adds `accepted_waste_label` and material-aware uniqueness to accepted waste rows; and extends collection requests with classification/center references, quantity, optional pickup coordinates, assigned staff, and internal notes. Existing center and request rows are preserved. Existing collection statuses stay as stored; new requests start in `pending`. Center removal is a soft deactivation.

Downgrading to Step 7 removes Step 8-only columns. Class-specific acceptance rows are deleted during downgrade because the old schema cannot represent them safely; legacy generic stream rows remain.

Admins create/update center records through the API and explicitly record verified status and accepted categories/material labels. No center data is seeded by this feature. Material labels use the Step 7 classes (Plastic, Paper / Cardboard, Metal, Glass, Organic / Food, Sanitary Products, Battery / E-Waste). Unknown items cannot be registered as an accepted material.

## Matching and location

Stream searches match only a generic stream acceptance row. Material searches and Step 7 recommendations match only the exact `accepted_waste_label` recorded for that center. Classification recommendations check the authenticated user's ownership, use the confirmed class when available, reject unconfirmed results that require confirmation, and return manual review for `Other / Unknown`.

Nearby search uses the Haversine great-circle formula and sorts by distance. It validates latitude/longitude and caps radius at 50 km. Centers missing coordinates are not assigned guessed distances and are excluded from radius-filtered results. City and postal-code search uses the stored center text fields and does not geocode. The browser requests precise location only after the user presses the location button; coordinates stay in page memory for the search and are not persisted. Optional pickup coordinates are only sent after the user opts in on the collection form.

The finder uses Leaflet 1.9.4 and OpenStreetMap tiles. The map draws only records with database coordinates. OSM attribution is visible, and the user is told that the map tile provider receives map requests. Tile use must follow the [OpenStreetMap tile usage policy](https://operations.osmfoundation.org/policies/tiles/). Leaflet is loaded from jsDelivr; internet access is needed for those assets and the map tiles.

## APIs

Center APIs are available under both the existing `/api/centers` prefix and the compatibility `/api/recycling-centers` prefix:

- `GET /api/recycling-centers?location=Pune&postal_code=411001&category=Dry%20waste`
- `GET /api/recycling-centers` supports `location` (city or postal text), `postal_code`, `category`, `waste_type`, and `center_type` filters; pagination uses `skip` and `limit`.
- `GET /api/recycling-centers/{center_id}`
- `GET /api/recycling-centers/nearby?latitude=...&longitude=...&radius_km=10&waste_type=Plastic`
- `GET /api/recycling-centers/recommendations/{classification_id}` (Bearer authentication required; accepts optional latitude/longitude/radius/location query fields)
- `POST /api/recycling-centers`, `PUT /api/recycling-centers/{center_id}`, `DELETE /api/recycling-centers/{center_id}` (admin only; delete deactivates)

Collection APIs remain under `/api/collection` and are also available under `/api/collections`:

- `POST /api/collections/requests`
- `GET /api/collections/requests` (users see their requests; collectors see assigned work; admins see all)
- `GET /api/collections/requests/{request_id}` (owner, assigned collector, or admin)
- `GET /api/collections/history` (authenticated user's own history)
- `PATCH /api/collections/requests/{request_id}/cancel`
- `PATCH /api/collections/requests/{request_id}/status`
- `PATCH /api/collections/requests/{request_id}/assign` (admin only)
- `GET /api/collections/requests/{request_id}/staff-details` (admin or assigned collector; includes internal notes/records)

Request creation accepts the existing `preferred_date` field and the alias `requested_date`, with an ISO future date. Optional fields include `waste_classification_id`, `recycling_center_id`, `quantity`, `quantity_unit`, `pickup_latitude`, and `pickup_longitude`. A classification must be owned by the requester and sufficiently confirmed. A selected center must be verified, active, and explicitly accept the selected category or exact confirmed material. Creating a request means it has been submitted for review; it does not claim that a pickup time is available.

## Status lifecycle, roles, and notifications

Allowed transitions are:

```text
pending → approved → assigned → scheduled → in_progress → completed
   ↘ rejected       ↘ cancelled (only from eligible states)
```

Pending requests may be approved/rejected by admins. Admins assign active collector accounts and schedule approved/assigned requests. Assigned collectors can start and complete their requests. Completion requires a collected quantity and writes a `collection_records` row. Request owners can cancel their own pending or approved requests. Invalid transitions fail with HTTP 409. Users cannot read another user's address; collector visibility is limited to assigned requests; internal notes and collection records are only exposed through the staff-details endpoint.

The existing in-app notifications and audit log are reused. Notifications are persisted for submission, approval/rejection, assignment, scheduling, start, completion, and cancellation. No email or SMS is sent.

## Dashboard and RAG

The dashboard reads existing summary/category aggregates, recent backend records, and a new administrator-only `/api/analytics/collection-operations` response. The operations panel shows actual counts for all lifecycle statuses and active/unverified centers. No frontend placeholder center, distance, request, or chart count is used. Non-admin users cannot load the admin operations totals.

The RAG assistant is unchanged and continues to use the existing retrieval and citation-validation path. Disposal guidance is grounded in indexed evidence. Center matching and availability always come from MySQL.

## Tests

After installing `backend/requirements.txt`, run:

```powershell
pytest
```

Tests use the existing isolated in-memory SQLite fixture. They cover center acceptance/distance, coordinate/radius validation, classification confirmation and ownership, collection lifecycle/assignment/records, status restrictions, notifications, and admin dashboard access. SQLite checks do not establish that a production MySQL instance has been migrated or is reachable. Verify production schema separately by applying Alembic to the configured MySQL database.

## Limitations

- This repository has no real recycling center records. An administrator must enter and verify real records and accepted material labels before searches can return matches.
- There is no geocoding provider; manual city/postal search is text matching. Radius search requires user-granted coordinates and stored center coordinates.
- Browser map assets/tiles require internet access and follow third-party service policies.
- Collection operations are in-app only. Email/SMS, dispatch capacity, staffing calendars, and live availability are not configured.
- Step 7 has no trained checkpoint in this checkout. Recommendations integrate with its database classifications, but image predictions remain unavailable until that model is trained and installed.
- No rate limiter exists in the current application; this change uses existing JWT auth, role checks, bounded pagination, and input constraints.
