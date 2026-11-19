# Neon PostgreSQL Setup

WasteWise AI uses synchronous SQLAlchemy. The app supports the existing MySQL/PyMySQL setup, SQLite test URLs, and PostgreSQL through psycopg 3. `DATABASE_URL` takes precedence when explicitly set; otherwise, the existing `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` variables construct the MySQL URL.

## Driver

`backend/requirements.txt` includes `psycopg[binary]>=3.2,<4`. PyMySQL remains installed so MySQL configuration continues to work during the transition. The app uses SQLAlchemy's connection pool; it does not create a second `psycopg_pool` pool.

## Configure a Neon connection

Copy `backend/.env.example` to `backend/.env`, then set `DATABASE_URL` locally to the connection URL copied from Neon. Use the explicit psycopg form:

```text
postgresql+psycopg://<user>:<password>@<endpoint>-pooler.<region>.aws.neon.tech:5432/wastewise_db?sslmode=require
```

Use the database name shown in Neon (the project can have a database name different from the example above). Keep SSL required. When constructing the URL manually, percent-encode reserved characters in the username and password; prefer the URL supplied by Neon. Do not paste credentials into source files, command history, logs, or reports. `.env` files are gitignored.

When `DATABASE_URL` is set, it overrides all MySQL `DB_*` settings. To switch back to MySQL, clear `DATABASE_URL` and configure the existing `DB_*` values. No MySQL settings or driver have been removed.

## Pooled and direct endpoints

For a persistent FastAPI application, use Neon’s pooled endpoint when connection pooling is enabled; the hostname normally contains `-pooler`. Neon’s pooler uses PgBouncer to multiplex client connections. The direct endpoint is useful for administrative tools and tasks that need a direct server connection. Select the endpoint from Neon’s connection details rather than editing a production host by hand. Neon documents pooled connections at [Connection pooling](https://neon.com/docs/connect/connection-pooling).

The application uses one SQLAlchemy pool per process. Its PostgreSQL defaults are five pooled connections and up to five overflow connections, with pre-ping enabled and connections recycled after five minutes. Multiply those limits by the number of application workers and adjust to the deployment’s Neon plan and concurrency.

## Run SQLite regression tests

The existing tests continue to override the database URL with an in-memory SQLite database and use their own `StaticPool` and foreign-key setup. From the repository root:

```powershell
$env:DEBUG = "false"
python -m pytest -q
```

The configuration tests parse URLs without connecting to MySQL or Neon. Do not set a production `DATABASE_URL` for the SQLite suite.

## PostgreSQL migration integration tests

Do not point these tests at the `production` branch or the existing `wastewise_db` database. In Neon, create a separate branch named for testing (for example, `wastewise-phase2-test`). Branches are isolated, but a branch created from production can contain a snapshot of its schema and data. Use a **new empty database** named `wastewise_test` inside the test branch; do not use the inherited production database. Neon branch isolation and copy-on-write behavior are described in its [branching guide](https://neon.com/blog/practical-guide-to-database-branching).

Install the project requirements in the project virtual environment (this includes psycopg 3):

```powershell
python -m pip install -r backend\requirements.txt
```

Set `POSTGRES_TEST_DATABASE_URL` to the pooled connection URL copied from the test branch’s `wastewise_test` database. Set the safety confirmation only after checking the branch and database names:

```powershell
$env:POSTGRES_TEST_DATABASE_URL = "<pooled URL for the disposable wastewise_test database>"
$env:POSTGRES_TEST_DATABASE_CONFIRMATION = "I_CREATED_A_DISPOSABLE_TEST_DATABASE"
```

Run the separate suite from the repository root:

```powershell
python -m pytest -q postgres_tests
```

It requires the explicit test URL and confirmation, rejects production-looking targets and database names without `test`, and refuses a database with existing application tables or records. For a previously tested target, it only cycles the migration history when the schema is exactly at head and every application table is empty. The suite upgrades all five revisions, verifies tables/constraints/IDs/JSON and ORM CRUD, then downgrades and upgrades again on that disposable target. It ends at head with an empty schema. Do not add `DATABASE_URL` as a fallback.

For migration history checks, first ensure `DATABASE_URL` points to the disposable test database (never production), then run from `backend`:

```powershell
alembic history
alembic current
```

Do not run `alembic upgrade head` manually against production. The PostgreSQL integration suite is the migration verification path for the isolated test target; production migration and MySQL data transfer are separate approval and planning steps.

## Migration and verification status

This phase only adds connection support. It does not connect to Neon or run migrations. The existing Alembic revisions were not rewritten and have not been verified against PostgreSQL. Before using Neon, test the full migration chain on a disposable PostgreSQL database or Neon branch, inspect the generated schema, and separately test data migration and application CRUD behavior. Existing MySQL records are not copied by Alembic.

Live PostgreSQL connectivity, SSL negotiation, pooling behavior, migration compatibility, and production data transfer remain unverified.
