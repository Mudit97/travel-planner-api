# AWS Constructs — What They Are and How They Connect

A reference for every AWS service and concept used in the travel-planner-api deployment. Each section explains what the construct is in isolation, then how it fits into this specific project.

---

## The Full Picture

```
Internet (browser / curl)
        |
        | HTTP port 8000
        |
 ┌──────▼──────────────────────────────────────────────┐
 │  EC2 Instance (travel-ecs-instance)                  │
 │  Amazon Linux 2 · t2.micro · ap-south-1             │
 │                                                      │
 │  ┌─────────────────────────────────────────────┐    │
 │  │  ECS Agent (daemon)                         │    │
 │  │  reads /etc/ecs/ecs.config                  │    │
 │  │  registered to: travel-planner-cluster      │    │
 │  └─────────────────────────────────────────────┘    │
 │                                                      │
 │  ┌─────────────────────────────────────────────┐    │
 │  │  ECS Task (travel-planner-task)             │    │
 │  │  Container: travel-api                      │    │
 │  │  Image: ECR → travel-planner-api:latest     │    │
 │  │  Port: 8000                                 │    │
 │  │  Env: DATABASE_URL → RDS endpoint           │    │
 │  └──────────────────────┬──────────────────────┘    │
 └─────────────────────────┼────────────────────────────┘
                           │
                           │ PostgreSQL port 5432 (SSL)
                           │
              ┌────────────▼───────────────────┐
              │  RDS PostgreSQL                 │
              │  travel-planner-db-1            │
              │  db.t4g.micro · ap-south-1      │
              │  database: travel_planner        │
              └────────────────────────────────┘

Developer machine (Mac)
        │
        │ docker push / aws cli
        │
 ┌──────▼──────────────────────┐
 │  ECR                        │
 │  travel-planner-api:latest  │
 │  ap-south-1                 │
 └─────────────────────────────┘
```

---

## IAM — Identity and Access Management

**What it is**: IAM is AWS's permission system. It controls who (users, services, applications) can do what (create EC2, push to ECR, read from S3) on which resources.

IAM is **global** — it is not scoped to any region. An IAM user, role, or policy exists across all regions.

### IAM User

A long-lived identity representing a human or application. Has credentials (password for console, access key for CLI/SDK). In this project: `travel-planner-dev`.

Rule: never use the root account for day-to-day work. Root can do anything including close the account — if compromised, there is no recovery.

### IAM Policy

A JSON document that lists allowed (or denied) actions. Attached to users or roles. Example:

```json
{
  "Effect": "Allow",
  "Action": ["ecr:GetAuthorizationToken", "ecr:BatchGetImage"],
  "Resource": "*"
}
```

Policies used in this project (attached to `travel-planner-dev`):
- `AmazonEC2ContainerRegistryFullAccess` — push/pull images from ECR
- `AmazonECS_FullAccess` — create clusters, services, task definitions
- `AmazonRDSFullAccess` — manage RDS instances
- `AmazonS3FullAccess` — upload/download from S3
- `CloudWatchFullAccess` — read/write logs

### IAM Role

Like a user, but meant to be **assumed** by a service or instance — not a human. Roles have no long-term credentials. Instead, AWS issues short-lived temporary credentials when the role is assumed.

Two roles in this project:

**ecsInstanceRole**
- Assumed by: EC2 instances in the ECS cluster
- Policy: `AmazonEC2ContainerServiceforEC2Role`
- What it enables: the ECS agent on the EC2 instance can register with the cluster, pull images from ECR, and write logs

**ecsTaskExecutionRole** (optional, used for Fargate or CloudWatch logging)
- Assumed by: the ECS service itself
- What it enables: pulling images from ECR on behalf of a task, writing container logs to CloudWatch

### IAM Instance Profile

A wrapper that attaches an IAM role to an EC2 instance. When you select `ecsInstanceRole` in the EC2 launch wizard under "IAM instance profile", you're creating this attachment. Software on the instance (like the ECS agent) automatically uses the role's permissions — no access keys needed.

---

## VPC — Virtual Private Cloud

**What it is**: A logically isolated private network in AWS. All your resources (EC2, RDS, ECS) live inside a VPC. AWS creates a **default VPC** in each region automatically — it has pre-configured subnets and routing tables, ready to use.

In this project we used the default VPC for simplicity. Week 4 (CDK) will create a custom VPC with proper public/private subnet separation.

### Subnets

A VPC is divided into subnets, each in a specific availability zone. The default VPC has one public subnet per AZ in the region. Resources in public subnets can have public IP addresses and be reached from the internet (if the security group allows it).

### Internet Gateway

Attached to the VPC, allows resources in public subnets to send and receive traffic from the internet. The default VPC already has one.

---

## Security Groups

**What it is**: A stateful virtual firewall that controls inbound and outbound traffic to AWS resources (EC2 instances, RDS, load balancers). Every resource must belong to at least one security group.

**Stateful** means: if you allow inbound traffic on port 8000, the return traffic (response) is automatically allowed — you don't need a separate outbound rule for it.

### Rules

Each rule specifies:
- **Type/Port**: which port (e.g. 8000, 5432, 22)
- **Protocol**: TCP, UDP
- **Source/Destination**: where traffic comes from (for inbound) or goes to (for outbound)
  - CIDR: `122.172.x.x/32` = a specific IP, `0.0.0.0/0` = anywhere
  - Security group ID: any resource in that security group (dynamic — works even if IPs change)

### Security groups in this project

**EC2 instance security group** (inbound):
| Port | Source | Purpose |
|---|---|---|
| 8000 | 0.0.0.0/0 | Public HTTP traffic to the API |
| 22 | My IP /32 | SSH access from developer Mac |

**RDS security group** (inbound):
| Port | Source | Purpose |
|---|---|---|
| 5432 | My IP /32 | Local dev — Mac connecting to RDS for Alembic migrations |
| 5432 | EC2 security group ID | ECS container → RDS |

Using a security group as a source (instead of an IP) is the correct pattern for service-to-service traffic. The IP of the EC2 instance can change; the security group membership doesn't.

---

## ECR — Elastic Container Registry

**What it is**: AWS's private Docker image registry. Stores Docker images inside your AWS account. ECS pulls images from ECR when starting tasks.

**Regional**: a repository in `ap-south-1` is not visible in `us-east-1`.

### How Docker authentication works with ECR

ECR doesn't use a static username/password. Instead, you request a short-lived token (12h TTL) via the AWS CLI and pipe it into `docker login`:

```bash
aws ecr get-login-password --region ap-south-1 \
  | docker login --username AWS --password-stdin \
    059674821864.dkr.ecr.ap-south-1.amazonaws.com
```

`--username AWS` is literal — always "AWS", never your IAM username.

### Image URI format

```
<account-id>.dkr.ecr.<region>.amazonaws.com/<repo-name>:<tag>
059674821864.dkr.ecr.ap-south-1.amazonaws.com/travel-planner-api:latest
```

Docker uses the prefix of the image name to decide which registry to push to. By tagging with the ECR URI (`docker tag` or `docker buildx build -t <ecr-uri>`), `docker push` knows to send to ECR.

### arm64 vs amd64

Mac M-series chips build `arm64` images by default. EC2 instances (except Graviton) are `amd64`. Always build explicitly for the target platform:

```bash
docker buildx build --platform linux/amd64 -t <ecr-uri>:latest --push .
```

---

## EC2 — Elastic Compute Cloud

**What it is**: Virtual machines (instances) running in AWS. You pick the OS (AMI), size (instance type), network (VPC/subnet), and IAM role. The instance runs 24/7 until you stop or terminate it.

### Instance in this project

- **Name**: `travel-ecs-instance`
- **AMI**: Amazon Linux 2 (includes the ECS agent pre-installed)
- **Type**: `t2.micro` (1 vCPU, 1 GB RAM — free tier for 12 months)
- **Key pair**: `travel-planner-key` (ED25519) — for SSH access
- **IAM profile**: `ecsInstanceRole`
- **User data**: shell script that runs on first boot, sets `ECS_CLUSTER=travel-planner-cluster` in `/etc/ecs/ecs.config`

### SSH access

```bash
ssh -i ~/.ssh/travel-planner-key.pem ec2-user@<public-ip>
```

The key file must be `chmod 400` (owner read-only) — SSH refuses to use keys that others can read.

### AMI — Amazon Machine Image

A pre-built OS snapshot. Amazon Linux 2 is the standard ECS-compatible AMI — it includes the ECS agent. Amazon Linux 2023 is newer but the ECS-optimized version may not appear in all console configurations; Amazon Linux 2 is the safe choice for ECS EC2 launch type.

---

## ECS — Elastic Container Service

**What it is**: AWS's container orchestration service. It schedules and runs Docker containers on EC2 instances (or Fargate). You define what to run (task definition) and ECS figures out where to place it and keeps it running.

### The hierarchy

```
ECS Cluster
  └── ECS Service
        └── ECS Task (running instance)
              └── Container (Docker container)
```

### Cluster

A logical grouping of EC2 instances (or Fargate capacity). The cluster itself is just a namespace — it has no compute of its own. Compute comes from the EC2 instances registered to it.

In this project: `travel-planner-cluster`

EC2 instances register to a cluster via the ECS agent reading `/etc/ecs/ecs.config`. The instance must also have `ecsInstanceRole` so the agent can authenticate with AWS.

**Self-managed vs managed instances**:
- Self-managed: you launch EC2 instances manually, they register themselves
- Managed: AWS creates an Auto Scaling Group that launches and registers instances automatically
- Fargate: no instances at all — AWS manages the compute entirely (costs more, no free tier)

### Task Definition

A blueprint (JSON document) that describes how to run a container:
- Which Docker image to use (ECR URI)
- CPU and memory to allocate
- Port mappings (container port → host port)
- Environment variables (DATABASE_URL, S3_BUCKET, etc.)
- IAM roles for the task
- Logging configuration

Task definitions are **immutable and versioned**. Every save creates a new revision (`travel-planner-task:1`, `travel-planner-task:2`). You can't edit a revision — you create a new one and update the service to point to it.

In this project: `travel-planner-task`
- OS/Architecture: Linux/X86_64
- Network mode: bridge (standard for EC2 launch type)
- Task CPU: 0.25 vCPU, Task memory: 0.5 GB
- Container: `travel-api`, port 8000, `DATABASE_URL` env var with `?sslmode=require`

### Service

Keeps a specified number of task copies running at all times. If a task crashes, the service restarts it. If you update the task definition, you update the service to use the new revision and it performs a rolling replacement.

In this project: `travel-api-service`, desired count = 1

**Deployment Circuit Breaker**: if a task fails to start repeatedly, ECS stops trying and marks the deployment as failed. Check the stopped task's logs to diagnose.

### Task

A running instance of a task definition. One task = one container (in our case). The task is placed on an EC2 instance in the cluster that has enough free CPU and memory.

---

## RDS — Relational Database Service

**What it is**: AWS's managed relational database. You pick the engine (PostgreSQL, MySQL, etc.) and instance size — AWS handles backups, patching, storage management, and high-availability failover.

You get a connection endpoint (hostname) that works exactly like a regular PostgreSQL server. Your app doesn't know or care that it's managed.

### In this project

- **Identifier**: `travel-planner-db-1`
- **Engine**: PostgreSQL
- **Instance**: `db.t4g.micro` (free tier)
- **Endpoint**: `travel-planner-db-1.c10460ausu7b.ap-south-1.rds.amazonaws.com`
- **Port**: 5432
- **Database name**: `travel_planner` (must be created manually — unlike Docker's `POSTGRES_DB` env var, RDS doesn't auto-create it)

### Key differences from Docker Postgres

| | Docker Postgres | RDS |
|---|---|---|
| Database auto-created | Yes (`POSTGRES_DB` env) | No — run `CREATE DATABASE` manually |
| SSL required | No | Yes — add `?sslmode=require` to connection URL |
| Access control | Any connection allowed | Security group must allow source IP/SG |
| Backups | None (data lost on `down -v`) | Automated daily backups, 7-day retention |

### SSL requirement

RDS rejects unencrypted connections. The `DATABASE_URL` must include `?sslmode=require`:

```
postgresql://travel_user:<pw>@<endpoint>:5432/travel_planner?sslmode=require
```

Without it: `FATAL: no pg_hba.conf entry for host ..., no encryption`

---

## How Everything Connects

```
Step 1 — Developer pushes code
  Mac → docker buildx build --platform linux/amd64 → ECR

Step 2 — ECS runs the container
  ECS Service → picks up travel-planner-task definition
             → schedules Task on travel-ecs-instance (EC2)
             → EC2 pulls image from ECR (allowed via ecsInstanceRole)
             → starts container on port 8000

Step 3 — Container connects to database
  Container reads DATABASE_URL env var from task definition
  → connects to RDS endpoint on port 5432 with SSL
  → RDS security group allows inbound from EC2 security group

Step 4 — User hits the API
  Browser → EC2 public IP:8000
  → EC2 security group allows inbound port 8000
  → request handled by FastAPI in the container
  → response returned

Step 5 — Schema changes
  Developer runs: alembic upgrade head (from Mac, pointing at RDS)
  → RDS security group allows inbound port 5432 from developer IP
  → migration applied
  → new image deployed via ECS service update
```

---

## Security Group Flow Diagram

```
Internet
    │ port 8000
    ▼
EC2 Security Group
(allows 0.0.0.0/0 on 8000)
    │
    ▼
EC2 Instance → ECS Task → container
    │
    │ port 5432
    ▼
RDS Security Group
(allows EC2 security group ID on 5432)
(allows developer IP on 5432)
    │
    ▼
RDS PostgreSQL
```

The key design principle: **nothing is open by default**. Every hop requires an explicit security group rule. Traffic flows only where you've explicitly permitted it.

---

## Quick Reference — Console Locations

| What | Where in console |
|---|---|
| IAM users / roles / policies | IAM (global — no region selector needed) |
| ECR repositories | ECR → ap-south-1 |
| ECS clusters / services / tasks | ECS → ap-south-1 |
| EC2 instances | EC2 → ap-south-1 |
| Security groups | EC2 → Security Groups (or VPC → Security Groups) |
| RDS instances | RDS → ap-south-1 |
| S3 buckets | S3 (global UI, but buckets are regional) |
