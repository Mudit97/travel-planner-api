# FAQ — Travel Planner API

Questions and discussions from the development session.

---

## Python Basics (coming from Java)

**Q: Python uses `null` like Java, right?**

No. Python's keyword is `None`, not `null`. `null` does not exist in Python and will raise a `NameError` at runtime. Similarly, Java's `&&` and `||` are `and` and `or` in Python.

```python
# Java
if (x == null) { ... }

# Python
if x is None: ...
```

Use `is None` / `is not None` for null checks, not `== None`. The `is` operator checks identity (same object), which is the correct way to check for `None`.

---

**Q: Do we need to import each name individually? Is there an `import *`?**

Python does have `from module import *`, but it's strongly discouraged. You can't tell where names came from, it can silently overwrite existing names, and linters flag it as an error.

The idiomatic Python way is to comma-separate names from the same module on one line:

```python
from app.models.trip import Trip, TripCreate, TripRead, TripUpdate
```

One `from x import` line per module, list all names you need. This is the equivalent of explicit Java imports — Python just lets you batch them.

---

## FastAPI & SQLModel

**Q: What do `session.add()`, `session.commit()`, and `session.refresh()` do?**

Think of `session` as a staging area between your Python code and the database.

- `session.add(obj)` — marks the object as pending. Nothing hits the database yet. You're telling SQLModel "track this, it needs saving."
- `session.commit()` — flushes everything pending to the database and ends the transaction. This is the moment the SQL `INSERT` or `UPDATE` actually runs. If anything fails, the whole transaction rolls back.
- `session.refresh(obj)` — after committing, the in-memory object may be stale (e.g. the DB set `id` via autoincrement). `refresh` re-fetches that row from the DB so your Python object reflects what's actually stored. Without it, returning a newly created object could give you `id=None`.

In short: **add** stages → **commit** persists → **refresh** syncs.

---

**Q: Are `session.add()`, `session.commit()`, `session.refresh()` FastAPI-specific or SQLModel-specific? Can we use them without FastAPI?**

They are **SQLModel/SQLAlchemy**, not FastAPI. FastAPI has nothing to do with them.

SQLModel is built on SQLAlchemy, a standalone Python ORM that works independently of any web framework. You can use sessions in a plain Python script:

```python
from sqlmodel import Session, create_engine

engine = create_engine("sqlite:///mydb.db")

with Session(engine) as session:
    trip = Trip(title="Paris", ...)
    session.add(trip)
    session.commit()
    session.refresh(trip)
```

The only FastAPI-specific part in the route handlers is `Depends(get_session)` — that's FastAPI's dependency injection system wiring the session into the handler automatically. The session itself is pure SQLAlchemy.

---

## Project-specific

**Q: Why did the server fail to start with `int | None` syntax?**

The `X | Y` union type syntax was introduced in Python 3.10. The project's virtual environment runs Python 3.9, so it raises a `TypeError` at import time. The fix is to use `Optional[int]` from the `typing` module instead:

```python
from typing import Optional

# Instead of: user_id: int | None = None
user_id: Optional[int] = None
```

---

**Q: When implementing a PATCH endpoint, how should date range validation work?**

You can't just check the two incoming dates against each other — the caller may only send one of them. You need to compute the effective values by falling back to the existing DB record:

```python
effective_start = trip.start_date or existingTrip.start_date
effective_end = trip.end_date or existingTrip.end_date
if effective_start > effective_end:
    raise HTTPException(status_code=400, detail="Invalid date range")
```

This ensures validation always sees the full picture regardless of which fields were sent.

---

**Q: What is the difference between `PUT` and `PATCH`?**

- `PUT` — full replacement. The caller must send all fields. Missing fields are treated as absent/null.
- `PATCH` — partial update. The caller sends only the fields they want to change. Other fields are left untouched.

For endpoints that accept optional fields and update only what's provided, `PATCH` is the correct HTTP method.

---

**Q: Why do `Optional` fields in a Pydantic/SQLModel schema need `= None`?**

`Optional[str]` only declares that the type *can* be `None` — it does not set a default. Without `= None`, Pydantic still requires the field to be present in the request body. Both are needed:

```python
class TripUpdate(SQLModel):
    title: Optional[str] = None       # correct — truly optional
    destination: Optional[str]        # wrong — still required by Pydantic
```

---

## Alembic

**Q: What is Alembic and why use it instead of `create_all()`?**

`create_all()` creates tables that don't exist yet but never modifies existing ones. If you add a column to a model, `create_all()` silently does nothing to the table already in the database. You'd have to run `ALTER TABLE` manually in every environment.

Alembic tracks schema changes as versioned migration files — like git commits for your database. Each migration has `upgrade()` (apply the change) and `downgrade()` (revert it). You run `alembic upgrade head` in any environment and it applies all missing migrations in order. Every developer, every server, every environment ends up with the exact same schema.

---

**Q: Why did Alembic autogenerate produce an empty migration even though I added a field?**

The field was declared as:

```python
budget: Optional[float] = None
```

Plain `= None` in Python looks like a class-level default value. SQLModel doesn't register it as a database column in SQLAlchemy's metadata. Autogenerate compares the current DB schema against `SQLModel.metadata` — if the column isn't in metadata, it's invisible to autogenerate.

Fix: use `Field(default=None)`:

```python
budget: Optional[float] = Field(default=None)
```

`Field()` explicitly registers the column in SQLAlchemy's metadata, so autogenerate sees it and generates the `ALTER TABLE`.

---

**Q: Does `create_db_and_tables()` in `main.py` conflict with Alembic?**

Not an immediate crash, but a problem in principle. `create_all()` skips tables that already exist, so if Alembic created the tables first, `create_all()` does nothing and there's no error.

The risk: if you add a new model and `create_all()` runs before you write an Alembic migration, it silently creates the table — bypassing Alembic entirely. Now Alembic's version history is out of sync with the actual DB.

Once you adopt Alembic, remove `create_db_and_tables()` from startup and let `alembic upgrade head` be the only thing that changes schema.

---

## PostgreSQL

**Q: `SELECT * FROM user` returns nothing in psql even though I created a user. Why?**

`user` is a reserved keyword in PostgreSQL. When you write `SELECT * FROM user`, Postgres interprets `user` as the SQL keyword (the currently connected database user), not your table name. It returns one row — the session user — or nothing, depending on context.

To query your `user` table, double-quote the name:

```sql
SELECT * FROM "user";
```

Double quotes preserve the exact identifier as-is. Unquoted identifiers are folded to lowercase and may be interpreted as keywords. This is a PostgreSQL-specific behaviour that SQLite doesn't have (SQLite has no reserved table name issue).

---

**Q: Is PostgreSQL case-sensitive?**

For identifiers (table names, column names): **no by default, yes if quoted**.

- Unquoted: `SELECT * FROM Trip` → Postgres lowercases it to `trip`
- Quoted: `SELECT * FROM "Trip"` → Postgres treats it as exactly `Trip` — case-sensitive

Since SQLModel creates tables with lowercase names by default, you should always use unquoted lowercase identifiers in raw SQL, except for reserved keywords like `user` which must be double-quoted.

For string data (values in `WHERE` clauses): case-sensitive by default.

```sql
WHERE title = 'Paris'   -- won't match 'paris'
WHERE lower(title) = 'paris'   -- case-insensitive match
```

---

## Docker & Docker Compose

**Q: Why can't the api container connect to Postgres using `localhost`?**

Inside a container, `localhost` means "this container itself". When the api container tries `localhost:5432`, it's looking for Postgres inside its own container, where nothing is listening on 5432.

In Docker Compose, all services share a private network and can reach each other by **service name**. Since the Postgres service is named `db` in `docker-compose.yml`, the api container reaches it at `db:5432`.

```
# .env for local dev (uvicorn on Mac)
DATABASE_URL=postgresql://travel_user:secret@localhost:5432/travel_planner

# .env for Docker Compose (api in container)
DATABASE_URL=postgresql://travel_user:secret@db:5432/travel_planner
```

---

**Q: If the app is running inside Docker, how can I access it at `localhost:8000`?**

Docker's port forwarding. The `ports: - "8000:8000"` in `docker-compose.yml` tells Docker to listen on your Mac's port 8000 and forward incoming traffic to port 8000 inside the container. Your browser connects to your Mac's network stack, not directly to the container.

The container itself isn't at `localhost` — Docker makes it appear that way through port mapping.

---

**Q: What is the `travel-planner-api_default` network that Docker Compose created?**

Docker Compose automatically creates a private virtual network for each project. All services in the `docker-compose.yml` are attached to it. This is how containers find each other by name (`db`, `api`) without exposing anything to the outside world. Traffic between containers stays on this internal network; only what you explicitly declare under `ports` is reachable from your Mac.

---

**Q: What is the `volumes: postgres_data` in `docker-compose.yml`?**

A named volume is a piece of storage Docker manages on your Mac, outside any container. Postgres stores its data files there. This means:

- `docker compose down` — containers removed, volume kept, **data survives**
- `docker compose up` — new containers attach to the same volume, data still there
- `docker compose down -v` — containers AND volume removed, **data gone**

Without a named volume, data would live inside the container layer and be lost whenever the container is removed.

---

## AWS & IAM

**Q: Why create a separate IAM user instead of using the root account?**

Your AWS root account is the "god mode" account — it can do absolutely anything, including closing the account, changing billing, and overriding all security policies. If root credentials are ever compromised, an attacker has total control with no way to lock them out.

IAM (Identity and Access Management) lets you create users with only the permissions they actually need. The `travel-planner-dev` user can push to ECR and manage ECS — but it can't change billing, delete the account, or touch other AWS services. If those credentials are leaked, the blast radius is limited.

Three rules that apply universally across all AWS projects:

1. **Never use root for day-to-day work.** Root is for initial account setup and emergencies only.
2. **Principle of least privilege.** Give each user/role only the permissions it actually needs.
3. **Rotate credentials regularly.** Access keys should be cycled periodically and immediately if exposed.

---

**Q: What is an AWS access key? How is it different from a password?**

Your AWS console password lets you log in via the browser. An access key lets programmatic tools (AWS CLI, boto3, SDKs) authenticate as you without a browser.

An access key has two parts:

| Part | Example | Purpose |
|---|---|---|
| Access Key ID | `AKIA...` | Identifies which key (like a username) |
| Secret Access Key | `WY8Iq...` | Proves you own the key (like a password) |

Both are needed together. The secret is only shown once at creation — if you lose it, you must delete the key and generate a new one.

`aws configure` stores both in `~/.aws/credentials` on your machine:

```ini
[default]
aws_access_key_id = AKIA...
aws_secret_access_key = WY8Iq...
region = ap-south-1
```

The CLI reads this file automatically — you don't pass the key on every command.

**Never put access keys in your project directory.** If they end up in a git commit, they're in history permanently and must be rotated immediately. GitHub actively scans for exposed AWS keys and notifies AWS — but the damage can happen within seconds of the push.

---

**Q: What does `aws sts get-caller-identity` do?**

`STS` is AWS Security Token Service. `get-caller-identity` returns who the current credentials belong to — Account ID, User ID, and ARN. It's the AWS equivalent of `whoami`. Use it to verify your CLI is configured correctly and pointing at the right account before running any real commands.

```json
{
    "UserId": "AIDA...",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/travel-planner-dev"
}
```

---

**Q: What is ECR and why not just use Docker Hub?**

ECR (Elastic Container Registry) is AWS's private Docker registry. When ECS pulls your container image to run it, it needs the image stored somewhere AWS can reach. ECR is:

- **Private** — only your AWS account (and roles you grant) can pull from it
- **In the same AWS network** — ECS pulls from ECR without going through the public internet, which is faster and has no egress cost
- **IAM-integrated** — access is controlled by IAM policies, not separate credentials

Docker Hub is public by default. You could use a private Docker Hub repo, but ECS would need separate credentials to pull from it — more configuration. ECR integrates seamlessly because ECS tasks already have IAM roles.

---

**Q: ECR is not visible in the AWS console even though I created it. Why?**

ECR is a regional service. A repository created in `ap-south-1` is only visible when the console's region selector (top-right corner of the AWS console) is set to `ap-south-1`. If you're looking at `us-east-1`, you'll see an empty repository list.

This applies to almost every AWS service: EC2 instances, RDS databases, ECS clusters — all scoped to the region they were created in. **IAM is the main exception** — users, roles, and policies are global and visible from any region.

Rule of thumb: if something you just created isn't showing up, check the region selector first.

---

**Q: What does `docker tag` do?**

`docker tag` creates an alias (another name) for an existing local image. It does not copy data or rebuild anything — both names point to the same image layers on disk.

```bash
docker build -t travel-planner-api .
# image stored locally as: travel-planner-api:latest

docker tag travel-planner-api:latest \
  059674821864.dkr.ecr.ap-south-1.amazonaws.com/travel-planner-api:latest
# now the same image is also known as the ECR URI
```

`docker push` uses the image name to decide where to push. Docker Hub images look like `nginx:latest` or `myuser/myapp:latest`. ECR images look like `<account>.dkr.ecr.<region>.amazonaws.com/<repo>:<tag>`. By tagging with the ECR URI, `docker push` knows to send it to ECR instead of Docker Hub.

---

**Q: Are AWS access keys tied to a specific region?**

No. Access keys belong to an IAM user, and IAM is a global service. A key created while the console was showing `us-east-1` works in `ap-south-1`, `eu-west-1`, or any other region. The console's region selector is just a UI preference — it doesn't restrict the key.

The region you set in `aws configure` (or `aws configure set region ap-south-1`) is the *default* region for CLI commands that don't specify one. You can always override it per-command with `--region <region>`.

---

**Q: What is a pre-signed URL in S3?**

S3 objects are private by default. A pre-signed URL is a time-limited URL that grants temporary read (or write) access to a specific object without making the bucket public.

When you call `s3.generate_presigned_url(...)`, AWS signs the URL with your credentials and an expiry time. Anyone with the URL can access the object until it expires — no AWS account needed. After expiry, the URL returns a 403 error.

Use cases:
- Return a signed URL to a client so they can download a private file directly from S3 (bypasses your server)
- Generate a signed upload URL so a client can upload directly to S3 (no file passes through your API)

```python
url = s3.generate_presigned_url(
    "get_object",
    Params={"Bucket": BUCKET, "Key": key},
    ExpiresIn=3600,   # expires in 1 hour
)
```
