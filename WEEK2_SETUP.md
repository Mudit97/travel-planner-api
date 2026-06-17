# Week 2 Setup — PostgreSQL + Docker

## What changed from Week 1

| | Week 1 | Week 2 |
|---|---|---|
| Database | SQLite (a file on disk) | PostgreSQL (a server process) |
| Location | `travel_planner.db` in project root | Inside a Docker container |
| Connection | Hardcoded path in `database.py` | `DATABASE_URL` env var read from `.env` |
| Driver | Built into Python stdlib | `psycopg2-binary` (installed separately) |
| Schema changes | `create_all()` on startup | Alembic migrations |
| App deployment | uvicorn on Mac directly | Docker Compose (api + db containers) |

---

## How the pieces connect

```
Your FastAPI app (uvicorn)
        |
        | reads DATABASE_URL from .env
        |
  app/database.py
        |
        | creates SQLAlchemy engine using the URL
        |
  psycopg2 (Python driver)
        |
        | TCP connection on localhost:5432
        |
  Docker container (travel_postgres)
        |
        | runs postgres:16-alpine image
        | database: travel_planner
        | user: travel_user / password: secret
```

---

## The DATABASE_URL format

```
postgresql://USER:PASSWORD@HOST:PORT/DB_NAME
postgresql://travel_user:secret@localhost:5432/travel_planner
```

- `postgresql://` — tells SQLAlchemy to use the Postgres dialect + psycopg2 driver
- `travel_user:secret` — credentials created when the container first started
- `localhost:5432` — Docker forwards container port 5432 to your Mac's localhost:5432 (the `-p 5432:5432` flag)
- `travel_planner` — the database name inside Postgres

In Week 1 the URL was `sqlite:///./travel_planner.db` — same format, different dialect, no credentials needed because SQLite is just a file.

---

## Why read from an environment variable?

`database.py` now does:

```python
DATABASE_URL = os.environ["DATABASE_URL"]
```

Instead of:

```python
DATABASE_URL = "sqlite:///./travel_planner.db"   # Week 1 hardcode
```

Three reasons:

1. **Different environments need different values.** Your local `.env` points to the Docker container. In production (Week 3) it will point to AWS RDS. You change the env var, not the code.

2. **Secrets don't belong in code.** A database URL contains a password. Hardcoding it means it ends up in git history forever. Env vars keep secrets out of source control — `.env` is gitignored.

3. **`os.environ["DATABASE_URL"]`** (with square brackets, not `.get()`) raises a `KeyError` immediately if the variable is missing. This is intentional — a missing DB URL should crash loudly at startup, not silently produce broken behaviour later.

---

## The Docker container

### What is Docker here?

Docker runs an isolated process (a container) from a pre-built image. `postgres:16-alpine` is the official Postgres image — it contains everything needed to run a Postgres server. You don't install Postgres on your Mac; the container has it.

### First-time setup — spinning up Postgres

Run this once to create and start the container:

```bash
docker run -d \
  --name travel_postgres \
  -e POSTGRES_USER=travel_user \
  -e POSTGRES_PASSWORD=secret \
  -e POSTGRES_DB=travel_planner \
  -p 5432:5432 \
  postgres:16-alpine
```

Verify it started correctly:

```bash
docker ps                          # should show travel_postgres as "Up"
docker logs travel_postgres        # look for "database system is ready to accept connections"
docker exec travel_postgres \
  pg_isready -U travel_user \
  -d travel_planner                # should print "accepting connections"
```

You only run `docker run` once. After that, use `docker start` / `docker stop` to manage it.

### The run command explained

```bash
docker run -d \                              # run in background (detached)
  --name travel_postgres \                  # name it so you can reference it later
  -e POSTGRES_USER=travel_user \            # env vars the image reads on first boot
  -e POSTGRES_PASSWORD=secret \             #   to create the superuser
  -e POSTGRES_DB=travel_planner \           #   and the initial database
  -p 5432:5432 \                            # forward Mac:5432 → container:5432
  postgres:16-alpine                        # image name:tag (alpine = small variant)
```

The three `-e` env vars are read by the Postgres image's entrypoint script on first boot. It creates the user and database automatically — you don't need to run any SQL manually.

### Useful Docker commands for this container

```bash
# Check it's running
docker ps

# See Postgres logs
docker logs travel_postgres

# Connect to it with psql (interactive shell inside container)
docker exec -it travel_postgres psql -U travel_user -d travel_planner

# Stop the container (data is preserved)
docker stop travel_postgres

# Start it again later
docker start travel_postgres

# Delete it entirely (data is lost)
docker rm -f travel_postgres
```

### Data persistence

The container stores Postgres data inside Docker's managed volume. If you `docker stop` and `docker start` the container, your data survives. If you `docker rm` it, the data is gone. In Week 3, we'll use a proper named volume and later move to RDS where AWS manages persistence.

---

## What happened at startup (the logs)

When `uvicorn` started and `create_db_and_tables()` ran, SQLAlchemy:

1. Connected to Postgres and checked which tables already existed
2. Found none (fresh DB)
3. Ran `CREATE TABLE` for `user`, `trip`, and `activity`
4. Committed

This is the same `SQLModel.metadata.create_all(engine)` call from Week 1 — but now it's talking to a real Postgres server instead of a SQLite file. The generated SQL looks different too: Postgres uses `SERIAL` for auto-increment IDs and `TIMESTAMP WITHOUT TIME ZONE` instead of SQLite's looser types.

This create-on-startup approach works for now, but it has a problem: if you ever need to *change* a table (add a column, rename a field), `create_all` won't touch existing tables. That's exactly what Alembic (Step 2) solves.

---

## Alembic — database migration versioning

### What is Alembic?

Alembic is a migration tool for SQLAlchemy. It tracks schema changes as versioned files (like git commits, but for your database schema). Every change — add a column, rename a table, add an index — becomes a numbered migration file with `upgrade()` and `downgrade()` functions.

Without Alembic: if you add a field to your model, you have to manually `ALTER TABLE` in every environment. With Alembic: you run `alembic upgrade head` and it applies all pending migrations automatically.

### How we set it up

1. Ran `alembic init alembic` — created `alembic/` directory and `alembic.ini`
2. Edited `alembic/env.py` to:
   - Import all models so SQLAlchemy knows about their tables
   - Point `target_metadata` at `SQLModel.metadata`
   - Read `DATABASE_URL` from the environment
3. Generated the first migration: `alembic revision --autogenerate -m "initial tables"` — was empty because tables already existed from `create_all()`
4. Applied it: `alembic upgrade head` — Alembic records the current version in the `alembic_version` table

### The `alembic/env.py` model imports

```python
import app.models.user      # noqa: F401
import app.models.trip      # noqa: F401
import app.models.activity  # noqa: F401

target_metadata = SQLModel.metadata
```

These imports are required even though we don't use the names directly. Importing the module causes Python to execute the class definitions, which registers the tables on `SQLModel.metadata`. Without these imports, autogenerate would see an empty metadata and think all tables should be dropped.

### Adding a new field — the workflow

```bash
# 1. Add the field to the model in Python
# 2. Generate the migration
alembic revision --autogenerate -m "add budget to trip"

# 3. Open the generated file in alembic/versions/ and verify the ALTER TABLE
# 4. Apply it
alembic upgrade head
```

The generated migration will contain:
```python
def upgrade() -> None:
    op.add_column('trip', sa.Column('budget', sa.Float(), nullable=True))

def downgrade() -> None:
    op.drop_column('trip', 'budget')
```

### Critical: use `Field()` for columns in SQLModel

```python
# WRONG — autogenerate will NOT detect this column
budget: Optional[float] = None

# CORRECT — Field() registers the column in SQLAlchemy metadata
budget: Optional[float] = Field(default=None)
```

Plain `= None` looks like a Python default value. `Field(default=None)` tells SQLModel "this is a database column with a default". Without `Field()`, `--autogenerate` produces an empty migration.

### `create_db_and_tables()` vs Alembic

Once you're using Alembic, `create_db_and_tables()` in `app/main.py` is redundant and potentially misleading:

```python
@app.on_event("startup")
def on_startup():
    create_db_and_tables()   # ← should be removed when using Alembic
```

`create_all()` skips existing tables, so there's no immediate crash — but it means new models could get created by `create_all()` without an Alembic migration, putting Alembic's version history out of sync with the actual DB. The correct approach is to remove this call and let Alembic be the sole owner of schema changes via `alembic upgrade head`.

### Viewing the DB after migrations

```bash
# Connect with psql
docker exec -it travel_postgres psql -U travel_user -d travel_planner

# List tables
\dt

# Describe a table (columns, types, constraints)
\d trip

# Check Alembic's version record
SELECT * FROM alembic_version;

# Query a table (note: "user" is a reserved word in Postgres — must quote it)
SELECT * FROM "user";
SELECT * FROM trip;
```

---

## Docker Compose — running everything together

### Why Docker Compose?

Previously we ran Postgres in a Docker container manually with `docker run`, and ran uvicorn directly on your Mac. Docker Compose lets you define both services in one file and start them together.

### The `docker-compose.yml`

```yaml
services:
  db:
    image: postgres:16-alpine
    container_name: travel_postgres
    environment:
      POSTGRES_USER: travel_user
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: travel_planner
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U travel_user -d travel_planner"]
      interval: 5s
      retries: 5

  api:
    build: .
    container_name: travel_api
    env_file:
      - .env
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy

volumes:
  postgres_data:
```

Key points:
- `build: .` — builds your app image from `Dockerfile` in the current directory
- `env_file: .env` — Compose reads `.env` from your Mac and injects values as env vars into the container
- `depends_on: condition: service_healthy` — api waits for Postgres to be ready before starting (not just "container up")
- `volumes: postgres_data` — named volume: data survives `docker compose down`, lost only on `docker compose down -v`

### The Docker network

When Compose starts, it creates a private network (`travel-planner-api_default`). Both containers join it automatically. Containers on the same network can reach each other by service name — so the api container reaches Postgres at `db:5432`, not `localhost:5432`.

```
Mac (your machine)
  │
  ├── localhost:8000  →  travel_api container :8000  (port forwarding)
  └── localhost:5432  →  travel_postgres container :5432  (port forwarding)
                              │
                    [Docker internal network]
                              │
                    travel_api → db:5432 → travel_postgres
```

### The critical `DATABASE_URL` difference

| Context | Host in DATABASE_URL |
|---|---|
| Uvicorn running on your Mac | `localhost` |
| Api running inside Docker Compose | `db` (the service name) |

Both reach the same Postgres container — but from different network perspectives. Update `.env` to `@db:5432` when using Docker Compose.

### Docker Compose commands

```bash
# Build image and start all services
docker compose up --build

# Start without rebuilding (code/env changes only)
docker compose down && docker compose up

# Stop and remove containers (data preserved in volume)
docker compose down

# Stop and remove containers AND volumes (data gone)
docker compose down -v

# View logs
docker compose logs -f

# View logs for one service
docker compose logs -f api
```

### How `localhost:8000` works when the app is in Docker

The `ports: - "8000:8000"` in `docker-compose.yml` tells Docker to forward your Mac's port 8000 into the container's port 8000. Your browser hits `localhost:8000`, Docker intercepts it and routes it to the container. The container is not "at" localhost — port forwarding makes it appear that way.

Same applies to `localhost:5432` for Postgres.

### `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- `FROM python:3.11-slim` — base image with Python already installed
- `COPY requirements.txt` then `RUN pip install` before `COPY . .` — this order means the pip layer is cached as long as `requirements.txt` doesn't change; only code changes trigger a rebuild
- `--host 0.0.0.0` — bind to all interfaces, not just loopback. Required inside containers — if you bind to `127.0.0.1`, port forwarding from Docker won't reach it.

### `.dockerignore`

```
.venv
.env
__pycache__
*.pyc
travel_planner.db
.git
```

Same idea as `.gitignore` — excludes files from being copied into the image. Critical entries:
- `.venv` — not needed in the image (pip installs directly into the container's Python)
- `.env` — secrets must never be baked into an image

---

## What happens to `.venv` and env vars when you Dockerize the app?

This is a common source of confusion, so it's worth understanding before Step 3.

### The virtual environment (`.venv`)

When you build a Docker image for the app, `.venv` is **not copied in and not used**. Here's why:

The point of a virtual environment is to isolate Python packages from the rest of your Mac. Docker already provides stronger isolation — the entire container is its own environment. You don't need a venv inside Docker.

Instead, the `Dockerfile` will look roughly like this:

```dockerfile
FROM python:3.11-slim          # base image already has Python
COPY requirements.txt .
RUN pip install -r requirements.txt   # installs directly into the container's system Python
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0"]
```

`pip install` runs at image build time and bakes the packages into the image layer. The `.venv` folder from your Mac is excluded via `.dockerignore` (same idea as `.gitignore`):

```
# .dockerignore
.venv
.env
__pycache__
*.pyc
travel_planner.db
```

**Summary:** `.venv` is a local-dev convenience. Docker replaces it with container-level isolation.

### Environment variables (`.env` and `export $(cat .env | xargs)`)

The `.env` file and the `export` trick we use locally are **also not used inside the image**. The `.env` file contains secrets — it should never be copied into an image (it would be baked in and visible to anyone who pulls it).

Instead, env vars are injected into the container at runtime, outside the image:

**Option 1 — `docker run` with `-e` flags** (what we did for Postgres):
```bash
docker run -e DATABASE_URL=postgresql://... travel-planner-api
```

**Option 2 — `docker-compose.yml` with `env_file`** (what we'll do in Step 3):
```yaml
services:
  api:
    env_file:
      - .env          # docker-compose reads .env on the HOST and injects the vars
```

The `.env` file stays on your machine and is never baked into the image. Docker Compose reads it at `docker compose up` time and passes the values as environment variables into the running container — the same way `export $(cat .env | xargs)` did for uvicorn locally.

**In production (Week 3):** you won't have a `.env` file on the server at all. Environment variables will be set directly on the EC2 instance or passed via AWS secrets management. Same `os.environ["DATABASE_URL"]` code, different source of truth.

**Summary:**

| | Local dev | Docker container |
|---|---|---|
| Packages | `.venv` | Baked into image via `pip install` in `Dockerfile` |
| Env vars | `.env` + `export $(cat .env \| xargs)` | `-e` flags or `env_file` in `docker-compose.yml` |
| Secrets in image? | N/A | Never — `.dockerignore` excludes `.env` |

---

## Starting the app (Week 2 final workflow)

### With Docker Compose (both api + db in containers)

```bash
# First time (or after code changes)
docker compose up --build

# Subsequent runs
docker compose up

# Stop everything
docker compose down
```

Swagger UI: http://localhost:8000/docs

### Local dev (uvicorn on Mac, Postgres in Docker)

```bash
# Ensure .env has DATABASE_URL pointing to localhost
# DATABASE_URL=postgresql://travel_user:secret@localhost:5432/travel_planner

docker start travel_postgres
export $(cat .env | xargs) && .venv/bin/uvicorn app.main:app --reload
```

### Running Alembic migrations

```bash
# Always load env vars first
export $(cat .env | xargs)

# Generate a new migration after changing a model
.venv/bin/alembic revision --autogenerate -m "describe your change"

# Apply all pending migrations
.venv/bin/alembic upgrade head

# Check current version
.venv/bin/alembic current
```
