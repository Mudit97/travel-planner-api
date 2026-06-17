# 4-Week Learning Resources

## Week 1 — Python + FastAPI

### Python (backend-relevant only)
- [Official Python Tutorial – Data Structures](https://docs.python.org/3/tutorial/datastructures.html) — lists, dicts, sets. Skim in 1 hour.
- [Real Python – Python Type Hints](https://realpython.com/python-type-checking/) — critical for FastAPI/Pydantic
- [Automate the Boring Stuff – Ch 1-6](https://automatetheboringstuff.com/) — if you want a linear read, just these chapters
- Your Java instinct: think `dict` = `HashMap`, `list` = `ArrayList`, no `null` (use `Optional[X]` or `X | None`)

### FastAPI
- [FastAPI Official Docs](https://fastapi.tiangolo.com/) — best framework docs in existence. Read "Tutorial" section end-to-end.
- [FastAPI – First Steps](https://fastapi.tiangolo.com/tutorial/first-steps/) — start here, run in 10 min
- [FastAPI – Path/Query Params, Request Body, Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/) — the 4 most important pages

### SQLModel (ORM used in this project)
- [SQLModel Docs](https://sqlmodel.tiangolo.com/) — same author as FastAPI, integrates perfectly
- [SQLModel – Relationships](https://sqlmodel.tiangolo.com/tutorial/relationship-attributes/) — understand this before Week 2

### Pydantic (validation)
- [Pydantic V2 Docs](https://docs.pydantic.dev/latest/) — just "Models" and "Validators" sections for now

### async/await
- [Real Python – Async IO](https://realpython.com/async-io-python/) — conceptual, skip the asyncio.run() deep dives
- For Week 1: you don't need async DB calls. Learn the syntax, use sync for now.

---

## Week 2 — PostgreSQL + Docker

### PostgreSQL
- [PostgreSQL Tutorial](https://www.postgresqltutorial.com/) — first 5 sections (connect, create table, CRUD, constraints, joins)
- [psql cheatsheet](https://quickref.me/postgres) — keep this open while practicing
- Your Java instinct: Postgres is just a more powerful MySQL. JDBC → psycopg2/asyncpg.

### SQLAlchemy 2.x (used under SQLModel)
- [SQLAlchemy 2.0 – ORM Quickstart](https://docs.sqlalchemy.org/en/20/orm/quickstart.html) — **use 2.x docs only**, older tutorials are wrong
- [SQLAlchemy – Session Basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)

### Alembic (migrations)
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html) — official, covers everything you need
- Mental model: Alembic = Flyway/Liquibase for Python

### Docker
- [Docker – Get Started](https://docs.docker.com/get-started/) — Parts 1-3 only
- [Docker – Dockerfile reference](https://docs.docker.com/reference/dockerfile/) — bookmark, don't memorize
- [Docker Compose – Getting Started](https://docs.docker.com/compose/gettingstarted/)
- [GitHub – tiangolo/full-stack-fastapi-template](https://github.com/tiangolo/full-stack-fastapi-template) — read the docker-compose.yml for inspiration, don't copy blindly

---

## Week 3 — AWS Deployment

### AWS Core Concepts
- [AWS – EC2 Getting Started](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EC2_GetStarted.html)
- [AWS – Security Groups](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-security-groups.html) — understand inbound/outbound rules
- [AWS – IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html) — skim, just learn "never use root, use roles"
- [AWS – RDS PostgreSQL](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_GettingStarted.CreatingConnecting.PostgreSQL.html)

### Practical Guides
- [DigitalOcean – How to Deploy FastAPI on Ubuntu + NGINX](https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-gunicorn-and-nginx-on-ubuntu) — Flask but same pattern, swap Flask for uvicorn
- [TestDriven.io – FastAPI + Docker + EC2](https://testdriven.io/blog/fastapi-docker-traefik/) — paid but worth it if you want a complete walkthrough
- [YouTube – TechWorld with Nana – Docker in 1 hour](https://www.youtube.com/watch?v=pg19Z8LL06w) — best free Docker visual explainer

### Linux/Server Basics (you'll need this for EC2)
- [OverTheWire Bandit](https://overthewire.org/wargames/bandit/) — gamified Linux CLI, do levels 0-10
- Key commands to know: `ssh`, `scp`, `systemctl`, `nginx -t`, `journalctl -f`, `top`, `df -h`

---

## Week 4 — Production Engineering

### Structured Logging
- [structlog docs](https://www.structlog.org/en/stable/) — Python's best logging library
- [12factor.net – Logs](https://12factor.net/logs) — 5-min read, changes how you think about logs

### Redis + Caching
- [Redis – Getting Started](https://redis.io/docs/get-started/)
- [redis-py docs](https://redis-py.readthedocs.io/en/stable/) — Python client
- [Real Python – Caching with Redis](https://realpython.com/python-redis/)

### API Design & Production Thinking
- [Google API Design Guide](https://cloud.google.com/apis/design) — bookmark, read "Resource Names" and "Errors" sections
- [FastAPI – Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [FastAPI – Middleware](https://fastapi.tiangolo.com/tutorial/middleware/) — add request timing here

### Monitoring Basics
- [Prometheus + FastAPI](https://github.com/trallnag/prometheus-fastapi-instrumentator) — drop-in metrics for FastAPI
- [Grafana Cloud free tier](https://grafana.com/products/cloud/) — visualize your metrics with zero infra

---

## Bonus: YouTube Channels
- **TechWorld with Nana** — Docker, K8s, cloud concepts (visual, beginner-friendly)
- **ArjanCodes** — Python architecture, clean code patterns
- **Fireship** — 100-second concept videos for quick orientation

## Bonus: GitHub Repos to Study
- [tiangolo/fastapi](https://github.com/fastapi/fastapi) — read the `examples/` folder
- [zhanymkanov/fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices) — community best practices, read after Week 1
