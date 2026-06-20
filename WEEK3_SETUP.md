# Week 3 Setup — AWS Core + Deploy

## What we're building this week

Taking the Dockerized app from Week 2 and deploying it to AWS. By the end of Week 3 the app runs entirely on AWS infrastructure — no local Docker Compose needed for "production".

| Step | Topic | What changes |
|---|---|---|
| 3.1 | IAM + AWS CLI + ECR | Push Docker image to AWS container registry |
| 3.2 | RDS | Replace Docker Postgres with managed AWS PostgreSQL |
| 3.3 | ECS (EC2 launch type) | Deploy the api container on AWS, wired to RDS |
| 3.4 | S3 | Add file upload endpoint (trip cover images) using boto3 |

---

## Architecture at the end of Week 3

```
Browser / curl
      |
      | HTTP :80
      |
 ECS EC2 instance
      | (runs travel_api container, pulled from ECR)
      |
      ├── DATABASE_URL → RDS PostgreSQL (managed, not in a container)
      └── S3 bucket    → trip cover images (boto3 uploads, signed URL reads)
```

---

## Step 3.1 — IAM + AWS CLI + ECR

### Why a separate IAM user?

Never use your AWS root account for day-to-day work. See FAQ for the full explanation.

### What we set up

- IAM user: `travel-planner-dev`
- Policies attached (managed):
  - `AmazonEC2ContainerRegistryFullAccess`
  - `AmazonECS_FullAccess`
  - `AmazonRDSFullAccess`
  - `AmazonS3FullAccess`
  - `CloudWatchFullAccess`
  - `SecretsManagerReadWrite`
- Access key generated and stored via `aws configure` (never in the project directory)

### AWS CLI configuration

```bash
aws configure
# AWS Access Key ID:     <from IAM console>
# AWS Secret Access Key: <from IAM console — only shown once>
# Default region name:   ap-south-1
# Default output format: json
```

This writes credentials to `~/.aws/credentials` — outside the repo, never committed.

If you already ran `aws configure` with a different region (e.g. `us-east-1`), fix it without re-entering all credentials:

```bash
aws configure set region ap-south-1
```

Access keys are **global** — they belong to the IAM user, not to any region. IAM is one of the few AWS services that is global. The region shown in the console when you created the key is just the UI's current region, not a restriction on where the key works.

Verify it works:

```bash
aws sts get-caller-identity
# Returns: Account ID, UserId, ARN of the configured user
```

### Security rules for credentials

- **Never** put access keys in project files
- **Never** commit `.csv` files or any file containing keys
- Add to `.gitignore`: `AWS_access_keys`, `*.csv`
- If a key is ever exposed (pushed to git, pasted in chat): delete it in IAM immediately and generate a new one
- Keys live in `~/.aws/credentials` only

### Create the ECR repository

ECR (Elastic Container Registry) is AWS's private Docker registry — like Docker Hub but inside your AWS account.

ECR is **regional** — a repository created in `ap-south-1` is only visible in the AWS console when the region selector (top-right) is set to `ap-south-1`. Switching to `us-east-1` will show an empty repository list even if you have repos in other regions.

```bash
aws ecr create-repository \
  --repository-name travel-planner-api \
  --region ap-south-1 \
  --image-scanning-configuration scanOnPush=true

# repositoryUri in the output — your ECR address:
# 059674821864.dkr.ecr.ap-south-1.amazonaws.com/travel-planner-api
```

`scanOnPush=true` tells ECR to automatically scan each image for known OS/package vulnerabilities when pushed.

### Authenticate Docker to ECR

```bash
aws ecr get-login-password --region ap-south-1 \
  | docker login --username AWS \
    --password-stdin \
    059674821864.dkr.ecr.ap-south-1.amazonaws.com
```

This pipes a short-lived token into `docker login`. The token expires after 12 hours — re-run this when it does. The `--username AWS` is literal (always "AWS"), not your IAM username.

### Build, tag, and push the image

```bash
# Build locally
docker build -t travel-planner-api .

# Tag with the full ECR URI
# docker tag <local-name> <ecr-uri>
docker tag travel-planner-api:latest \
  059674821864.dkr.ecr.ap-south-1.amazonaws.com/travel-planner-api:latest

# Push to ECR
docker push \
  059674821864.dkr.ecr.ap-south-1.amazonaws.com/travel-planner-api:latest
```

**Why `docker tag`?** `docker build -t travel-planner-api .` stores the image locally under the name `travel-planner-api:latest`. Docker determines *where* to push based on the image name — the registry URL must be embedded in it. `docker tag` creates an alias pointing to the same image data with the ECR URL as the name. No data is duplicated; both names reference the same image layers. Without this step, `docker push travel-planner-api:latest` would try to push to Docker Hub.

```bash
# Verify both names point to the same image ID
docker images | grep travel-planner-api
```

Verify in the console: ECR → Repositories → travel-planner-api (in ap-south-1) → should show the `latest` image with a scan status.

---

## Step 3.2 — RDS PostgreSQL

### What is RDS?

RDS (Relational Database Service) is AWS's managed database. AWS handles backups, patching, failover, and storage. You get a PostgreSQL endpoint URL — same as what psycopg2 connects to, just at a different host.

### What changes from Week 2

| | Week 2 | Week 3 |
|---|---|---|
| Postgres runs in | Docker container on your Mac | RDS instance on AWS |
| Host in DATABASE_URL | `localhost` or `db` | RDS endpoint (e.g. `travel.xxxxx.ap-south-1.rds.amazonaws.com`) |
| Managed by | You | AWS (backups, patching, HA) |
| Cost | Free (Docker) | Free tier: db.t3.micro for 12 months |

### Provision via AWS Console

1. RDS → **Create database**
2. Engine: **PostgreSQL** (latest 16.x)
3. Template: **Free tier**
4. DB instance identifier: `travel-planner-db`
5. Master username: `travel_user`
6. Master password: set a strong password (not `secret`)
7. Instance class: `db.t3.micro` (free tier)
8. Storage: 20 GB gp2 (free tier)
9. **Connectivity**: VPC — default VPC for now; Public access: **Yes** (for Week 3 learning — lock this down in production)
10. Create a new security group: `travel-rds-sg`
11. Create database

### Allow connections from your IP

Once created:
1. Click into the RDS instance → **Connectivity & security** → VPC security groups → click the group
2. **Inbound rules** → **Edit** → **Add rule**
   - Type: PostgreSQL
   - Port: 5432
   - Source: **My IP** (for local access) + later the ECS security group

### Run Alembic migrations against RDS

```bash
# Point DATABASE_URL at RDS (update .env temporarily or export directly)
export DATABASE_URL=postgresql://travel_user:<password>@<rds-endpoint>:5432/travel_planner

# Create the database first (RDS doesn't create it automatically like Docker did)
psql postgresql://travel_user:<password>@<rds-endpoint>:5432/postgres \
  -c "CREATE DATABASE travel_planner;"

# Run migrations
.venv/bin/alembic upgrade head
```

### Test the connection

```bash
psql postgresql://travel_user:<password>@<rds-endpoint>:5432/travel_planner
\dt   # should show user, trip, activity, alembic_version tables
```

---

## Step 3.3 — ECS (EC2 launch type)

### What is ECS?

ECS (Elastic Container Service) is AWS's container orchestration service — it runs your Docker containers on AWS infrastructure. We use the **EC2 launch type** (free tier eligible) rather than Fargate (no free tier).

```
ECS Cluster
  └── ECS Service
        └── ECS Task (one or more)
              └── Container (your travel-planner-api image from ECR)
```

- **Cluster**: logical grouping of EC2 instances
- **Task Definition**: blueprint for a container — image, CPU, memory, env vars, ports
- **Service**: keeps N copies of a task running, restarts on failure
- **Task**: a running instance of the task definition (= a container)

### Architecture note: arm64 vs amd64

If you're on an Apple Silicon Mac (M1/M2/M3), Docker builds `arm64` images by default. ECS EC2 instances run `amd64` (x86_64). You must rebuild for the correct architecture before pushing:

```bash
# Re-authenticate to ECR first (token expires after 12h)
aws ecr get-login-password --region ap-south-1 \
  | docker login --username AWS \
    --password-stdin \
    059674821864.dkr.ecr.ap-south-1.amazonaws.com

# Build for amd64 and push directly to ECR
docker buildx build --platform linux/amd64 \
  -t 059674821864.dkr.ecr.ap-south-1.amazonaws.com/travel-planner-api:latest \
  --push \
  .
```

If `buildx` isn't set up: `docker buildx create --use` then re-run the build command.

### Step 1 — Create IAM instance profile (ecsInstanceRole)

EC2 instances in an ECS cluster need an IAM role so the ECS agent can authenticate with ECS and pull images from ECR.

IAM → Roles → **Create role**:
- Trusted entity: **EC2**
- Policy: `AmazonEC2ContainerServiceforEC2Role`
- Role name: `ecsInstanceRole`

### Step 2 — Create the ECS Cluster

ECS → Clusters → **Create cluster**:
- Cluster name: `travel-planner-cluster`
- Infrastructure: **Fargate and self-managed instances** (shows EC2 configuration options)
- With self-managed instances, AWS does NOT launch EC2 instances for you — you launch them manually and they register themselves to the cluster via the ECS agent.

### Step 3 — Launch the EC2 instance

EC2 → **Launch Instance**:

| Field | Value |
|---|---|
| Name | `travel-ecs-instance` |
| AMI | Amazon Linux 2 |
| Instance type | `t2.micro` (free tier) |
| Key pair | Create new → `travel-planner-key`, ED25519, `.pem` |
| Security group | Use the one with port 8000 + port 22 open inbound |
| IAM instance profile | `ecsInstanceRole` |

In **Advanced details → User data** (critical — tells the instance which cluster to join):
```bash
#!/bin/bash
echo ECS_CLUSTER=travel-planner-cluster >> /etc/ecs/ecs.config
```

Save the `.pem` key file to `~/.ssh/` and restrict permissions:
```bash
mkdir -p ~/.ssh
mv ~/Downloads/travel-planner-key.pem ~/.ssh/travel-planner-key.pem
chmod 400 ~/.ssh/travel-planner-key.pem
```

`chmod 400` — owner read-only, no access for group/others. SSH refuses to use a key file that others can read.

### Step 4 — Verify instance registered to cluster

**ECS → Clusters → travel-planner-cluster → Infrastructure tab** — instance should appear within 1-2 minutes.

If the instance doesn't appear, SSH in and check:
```bash
ssh -i ~/.ssh/travel-planner-key.pem ec2-user@<public-ip>

# Check if ECS agent is running
sudo systemctl status ecs

# Check/set the cluster config
cat /etc/ecs/ecs.config

# If file is missing or empty:
echo ECS_CLUSTER=travel-planner-cluster | sudo tee /etc/ecs/ecs.config
sudo systemctl restart ecs
```

### Step 5 — Open port 8000 on the EC2 security group

The EC2 instance's security group needs inbound port 8000 so traffic from the internet reaches the container.

EC2 → Security Groups → the group attached to `travel-ecs-instance` → **Edit inbound rules → Add rule**:

| Type | Port | Source |
|---|---|---|
| Custom TCP | 8000 | 0.0.0.0/0 |
| SSH | 22 | My IP |

Also add the ECS security group ID as an inbound source in the **RDS security group** on port 5432, so ECS containers can reach RDS:

| Type | Port | Source |
|---|---|---|
| PostgreSQL | 5432 | `<ecs-instance-security-group-id>` |

### Step 6 — Create the Task Definition

ECS → Task definitions → **Create new task definition**:

| Field | Value |
|---|---|
| Task definition name | `travel-planner-task` |
| Launch type | EC2 |
| OS/Architecture | Linux/X86_64 |
| Network mode | bridge |
| Task CPU | 0.25 vCPU |
| Task memory | 0.5 GB |

Container - 1:

| Field | Value |
|---|---|
| Name | `travel-api` |
| Essential | Yes |
| Image URI | `059674821864.dkr.ecr.ap-south-1.amazonaws.com/travel-planner-api:latest` |
| Container port | 8000 / tcp |
| Port name | (leave blank) |
| App protocol | (leave blank) |

Environment variables:
```
DATABASE_URL = postgresql://travel_user:<password>@travel-planner-db-1.c10460ausu7b.ap-south-1.rds.amazonaws.com:5432/travel_planner?sslmode=require
```

`?sslmode=require` is mandatory — RDS rejects unencrypted connections by default.

### Step 7 — Create the ECS Service

ECS → Clusters → travel-planner-cluster → Services → **Create**:

| Field | Value |
|---|---|
| Launch type | EC2 |
| Task definition | `travel-planner-task` (latest) |
| Service name | `travel-api-service` |
| Desired tasks | 1 |

### Step 8 — Verify

**ECS → Clusters → travel-planner-cluster → Services → travel-api-service → Tasks tab** — task should show **RUNNING**.

If the task fails (Deployment Circuit Breaker triggered), click the stopped task → Logs tab to read the error. Common causes:
- Wrong password in `DATABASE_URL` → create a new task definition revision with the correct password
- Missing `?sslmode=require` → update `DATABASE_URL` in a new revision
- Port 8000 not open on EC2 security group

Once RUNNING, hit Swagger:
```
http://<ec2-public-ip>:8000/docs
```

### Updating the deployment

When you push a new image to ECR:
```bash
# 1. Build and push
docker buildx build --platform linux/amd64 \
  -t 059674821864.dkr.ecr.ap-south-1.amazonaws.com/travel-planner-api:latest \
  --push .

# 2. Force ECS to restart the task with the new image
aws ecs update-service \
  --cluster travel-planner-cluster \
  --service travel-api-service \
  --force-new-deployment
```

When you update environment variables (e.g. DATABASE_URL):
- ECS → Task Definitions → travel-planner-task → **Create new revision** → update env var → save
- ECS → Services → travel-api-service → **Update** → select new revision → save

---

## Step 3.4 — S3 (File uploads)

### What is S3?

S3 (Simple Storage Service) is AWS's object storage. You store files (objects) in buckets. We'll use it to store trip cover images uploaded by users.

### Flow

```
Client uploads image
      ↓
POST /trips/{id}/image  (FastAPI endpoint)
      ↓
boto3 uploads to S3 bucket
      ↓
Returns a pre-signed URL the client can use to view the image
```

### Create the bucket

```bash
aws s3api create-bucket \
  --bucket travel-planner-images-<your-account-id> \
  --region ap-south-1 \
  --create-bucket-configuration LocationConstraint=ap-south-1
```

Bucket names are globally unique — append your account ID to avoid conflicts.

### Install boto3

```bash
.venv/bin/pip install boto3
# add to requirements.txt: boto3==1.34.0
```

### Add the upload endpoint

```python
# app/routers/trips.py
import boto3
from fastapi import UploadFile, File

s3 = boto3.client("s3", region_name="ap-south-1")
BUCKET = os.environ["S3_BUCKET"]

@router.post("/{trip_id}/image")
def upload_trip_image(trip_id: int, file: UploadFile = File(...)):
    key = f"trips/{trip_id}/{file.filename}"
    s3.upload_fileobj(file.file, BUCKET, key)
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=3600,
    )
    return {"url": url}
```

Add `S3_BUCKET` to `.env` and as an ECS task environment variable.

### Pre-signed URLs

A pre-signed URL is a temporary URL that grants read access to a private S3 object without making the bucket public. It expires after `ExpiresIn` seconds (3600 = 1 hour above). After expiry, the URL returns 403.

---

## Week 3 workflow

### Local development (still works)

```bash
# Postgres: either local Docker or point at RDS
docker compose up          # local Docker Compose
# or
export DATABASE_URL=postgresql://...rds... && uvicorn app.main:app --reload

# AWS credentials needed for S3 uploads even locally
aws configure              # already done
```

### Deploy changes to ECS

```bash
# 1. Build and push new image
docker build -t travel-planner-api .
docker tag travel-planner-api:latest $ECR_URI:latest
docker push $ECR_URI:latest

# 2. Force ECS to pull the new image
aws ecs update-service \
  --cluster travel-planner-cluster \
  --service travel-api-service \
  --force-new-deployment
```

ECS stops the old task and starts a new one pulling `:latest` from ECR.

### Run Alembic migrations on schema changes

Always run migrations before deploying new code that depends on new columns:

```bash
export DATABASE_URL=postgresql://...rds...
.venv/bin/alembic upgrade head
# then deploy the new image
```

---

## CDK preview (coming in Week 4)

Everything done manually above (RDS, ECS cluster, task definition, S3 bucket, IAM roles, security groups) will be replaced with CDK TypeScript stacks in Week 4. The manual setup is intentional — understanding what you're creating makes the CDK abstractions meaningful rather than magic.
