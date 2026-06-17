## Quick reference — Travel Planner API

Checklist
- Virtual environment (venv)
- .env and DATABASE_URL
- ASGI / uvicorn
- SQLModel and the SQLite database
- How tables are created at startup
- Dependency management (requirements.txt)
- Useful sqlite3 commands
- Start / stop the server

Key points (short)
- Virtual environment: a project-local Python environment that keeps packages isolated. Common name: `.venv` but any name works. Create: `python3 -m venv .venv`. Activate: `source .venv/bin/activate`. Deactivate: `deactivate`.
- .env: keep runtime configuration and secrets out of source control. Copy `.env.example` to `.env` and edit values. Load from Python with `python-dotenv` or `pydantic.BaseSettings`.
- ASGI & uvicorn: ASGI is the async server interface. This project uses `uvicorn` to run FastAPI. Dev run: `uvicorn app.main:app --reload`.
- SQLModel: combines SQLAlchemy + Pydantic. Define models in `app/models/*.py`. Use `session.exec(...)`, `session.add()`, `session.commit()` and `session.refresh()` in route handlers.
- Database location: default `DATABASE_URL` is `sqlite:///./travel_planner.db` -> a file named `travel_planner.db` in the project root (persistent on disk). An in-memory DB uses `sqlite:///:memory:` (ephemeral).
- Table creation: `app.database.create_db_and_tables()` calls `SQLModel.metadata.create_all(engine)`. `app.main` calls this at startup (`@app.on_event("startup")`) so tables are created when the app starts (ensure model modules are imported before this runs).
- Engine logging: `create_engine(..., echo=True)` prints generated SQL statements to the console (helpful in development; disable in production).
- Sessions: `get_session()` yields a `Session(engine)` to route handlers (used with `Depends`) and ensures the session is closed after each request.
- Dependencies: this project uses `requirements.txt`. Install with `pip install -r requirements.txt`. After adding packages run `pip freeze > requirements.txt` to pin versions.

Useful sqlite3 commands
- Open interactive shell: `sqlite3 ./travel_planner.db`
- Inside shell:
	- `.tables` — list tables
	- `.schema TABLE_NAME` — show CREATE TABLE
	- `PRAGMA table_info('TABLE_NAME');` — show columns
	- `SELECT * FROM users LIMIT 10;` — view rows
	- `.dump` — SQL dump of DB
- From terminal (one-off):
	- `sqlite3 ./travel_planner.db ".tables"`
	- `sqlite3 -header -column ./travel_planner.db "SELECT * FROM users LIMIT 5;"`
	- `sqlite3 ./travel_planner.db .dump > dump.sql`
	- `sqlite3 ./travel_planner.db "PRAGMA integrity_check;"`

Start / stop server (common commands)
- Start (dev):
	```bash
	uvicorn app.main:app --reload
	```
- Stop when running in foreground: press `Ctrl+C`.
- Find / stop processes by port (default 8000):
	```bash
	lsof -ti TCP:8000 | xargs kill    # graceful
	pgrep -f uvicorn | xargs kill     # kill by name
	pgrep -f uvicorn | xargs kill -9  # force (only if needed)
	```

Quick commands (copyable)
```bash
# create and activate venv
python3 -m venv .venv
source .venv/bin/activate

# install dependencies
pip install -r requirements.txt

# create DB tables manually (optional)
python -c "from app.database import create_db_and_tables; create_db_and_tables()"

# run the app
uvicorn app.main:app --reload

# inspect DB
sqlite3 -header -column ./travel_planner.db "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
```

Where to look in the code
- `app/main.py` — FastAPI app, startup event, routers included
- `app/database.py` — engine, `create_db_and_tables()`, `get_session()`
- `app/models/*.py` — SQLModel model definitions (tables and schemas)
- `app/routers/*.py` — route handlers using `Depends(get_session)`

Next steps / tips
- Add `.venv` to `.gitignore`.
- Move `DATABASE_URL` into `.env` and read it from the environment for easier switching to Postgres later.
- When switching to SQLite with FastAPI/ASGI, set `connect_args={"check_same_thread": False}` when creating the engine.

That's a compact summary of what we covered. If you want, I can expand any section into a longer how-to or apply the small improvements (env loading, connect_args) to the code.

# Travel Planner API

A FastAPI project built as part of a 4-week backend upskilling plan.

## Stack
- **Week 1**: Python · FastAPI · SQLite · SQLModel
- **Week 2**: PostgreSQL · Alembic · Docker
- **Week 3**: AWS EC2 · RDS · NGINX
- **Week 4**: Redis · structured logging · health checks

---

## Setup (Week 1)

```bash
# 1. Create virtual env
python3 -m venv .venv
source .venv/bin/activate

# 2. Install deps
pip install -r requirements.txt

# 3. Run
uvicorn app.main:app --reload
```

API docs auto-generated at: http://localhost:8000/docs

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /users/ | Create a user |
| GET | /users/{id} | Get user by ID |
| GET | /users/ | List all users |
| POST | /trips/ | Add a trip |
| GET | /trips/{id} | Get trip by ID |
| GET | /trips/{id}/itinerary | Get all activities for a trip |
| GET | /trips/?user_id= | Filter trips by user |
| POST | /activities/ | Add an activity to a trip |
| GET | /activities/{id} | Get activity by ID |
| DELETE | /activities/{id} | Delete an activity |
| GET | /health | Health check |

---

## Project Structure

```
travel-planner-api/
├── app/
│   ├── main.py          # App entry point, routers registered here
│   ├── database.py      # DB engine + session dependency
│   ├── models/
│   │   ├── user.py      # User table + Create/Read schemas
│   │   ├── trip.py      # Trip table + schemas
│   │   └── activity.py  # Activity table + schemas
│   └── routers/
│       ├── users.py
│       ├── trips.py
│       └── activities.py
├── requirements.txt
├── .env.example
└── README.md
```

---

## Week-by-Week Upgrades

### Week 2
- [ ] Swap SQLite → PostgreSQL in `database.py`
- [ ] Add Alembic: `alembic init alembic`
- [ ] Write `Dockerfile` + `docker-compose.yml`

### Week 3
- [ ] Launch EC2 (Ubuntu), install Docker
- [ ] Push image, `docker compose up` on server
- [ ] Move DB to RDS, update `DATABASE_URL`
- [ ] Set up NGINX as reverse proxy

### Week 4
- [ ] Add Redis caching for itinerary endpoint
- [ ] Structured JSON logging with `structlog`
- [ ] `/metrics` endpoint (request count, latency)
- [ ] Global exception handler with proper error responses
