# WasteWise AI – MySQL Database Setup (Step 4)

This guide configures MySQL persistence for the FastAPI backend. Tables are created with Alembic. The application does not drop or recreate tables on startup.

## 1. MySQL installation requirements

Install MySQL 8.x (Community Server) for Windows, macOS, or Linux.

Confirm the service is running and that you can connect as a local user:

```bash
mysql --version
mysql -u root -p
```

Python dependencies (from `backend/requirements.txt`) include:

- SQLAlchemy
- PyMySQL
- python-dotenv
- Alembic
- cryptography

## 2. Create the application database

```sql
CREATE DATABASE wastewise_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Optional isolated test database (never point destructive tests at `wastewise_db` in production):

```sql
CREATE DATABASE wastewise_test_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

## 3. Environment configuration

From the `backend` directory:

```bash
copy .env.example .env
```

On macOS/Linux:

```bash
cp .env.example .env
```

Edit `.env` and set real values. Do not commit `.env`.

```env
DB_HOST=localhost
DB_PORT=3306
DB_NAME=wastewise_db
DB_USER=root
DB_PASSWORD=your_password

JWT_SECRET_KEY=replace_with_secure_secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

`core/config.py` builds:

`mysql+pymysql://USER:PASSWORD@HOST:PORT/DB_NAME`

## 4. Python environment

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

On macOS/Linux activate with `source venv/bin/activate`.

## 5. Alembic migrations

Run commands from the `backend` directory so `alembic.ini` is found.

```bash
alembic upgrade head
```

Create additional revisions after model changes:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

Roll back one revision only when you intend to:

```bash
alembic downgrade -1
```

Revision `20261117_0001` creates:

- users
- roles
- waste_categories
- waste_reports
- recycling_centers
- accepted_waste_types
- collection_requests
- collection_records
- notifications
- audit_logs

Revision `20261117_0002` adds Step 5 knowledge-base metadata tables:

- knowledge_documents
- document_versions
- document_chunks
- ingestion_jobs

Revision `20261117_0003` adds authenticated assistant conversation and message history.

## 6. Seed commands

Seed **roles** (`admin`, `citizen`, `collector`) and **waste categories** only. The seed script does not insert invented recycling facilities.

```bash
cd backend
python scripts/seed_db.py
```

The API also inserts missing roles and categories on startup if the tables already exist.

## 7. Backend execution

```bash
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open:

- API: http://127.0.0.1:8000
- Health: http://127.0.0.1:8000/health
- Swagger: http://127.0.0.1:8000/docs

Serve the existing HTML frontend separately (for example Live Server on port 5500). Frontend `fetch` paths are unchanged.

## 8. Database verification

In MySQL:

```sql
USE wastewise_db;
SHOW TABLES;
SELECT role_name FROM roles;
SELECT category_name FROM waste_categories;
SELECT id, email FROM users;
SELECT id, title, report_status FROM waste_reports;
SELECT id, status FROM collection_requests;
```

`GET /health` should report `"database": "connected"`.

Register a user via `POST /api/auth/register`, restart the backend, and confirm the row is still present. Repeat with waste reports and collection requests.

## 9. Automated tests

From the repository root (isolated SQLite; does not mutate `wastewise_db`):

```bash
cd backend
venv\Scripts\activate
cd ..
python -m pytest tests -q
```

Optional live MySQL check against your configured database:

```bash
set WASTEWISE_RUN_MYSQL_TESTS=1
python -m pytest tests/test_database.py::test_mysql_connection_optional -q
```

Do not run that optional test against a production database you cannot afford to inspect.

## 10. Common connection errors

| Symptom | Likely cause | What to do |
| --- | --- | --- |
| `Can't connect to MySQL server on 'localhost'` | MySQL service is stopped or bound to another host | Start MySQL and confirm `DB_HOST` / `DB_PORT` |
| `Access denied for user` | Wrong user or password | Update `DB_USER` / `DB_PASSWORD` in `.env` |
| `Unknown database 'wastewise_db'` | Database was not created | Run the `CREATE DATABASE` statement above |
| `No module named 'pymysql'` | Dependencies not installed | `pip install -r requirements.txt` |
| Seed or API error about missing role/category | Migrations or seed not applied | `alembic upgrade head` then `python scripts/seed_db.py` |
| `1045` / `2003` in the terminal | Credentials or network | The API hides raw SQL errors from HTTP clients; check backend logs, not the JSON body |
| Alembic `Can't locate revision` | Wrong working directory | Run Alembic from `backend/` |

If the API returns HTTP 503 with “database is temporarily unavailable”, the engine could not complete a connectivity probe. Fix MySQL first, then retry.
