# EV Research - Infrastructure Setup Guide

Follow these steps in order. Each step must complete before the next.

---

## Prerequisites

- Windows 10/11, PowerShell 5+
- Admin rights on your machine
- A DigitalOcean account (https://cloud.digitalocean.com)
- Credit card added to DO (required to create resources)

---

## Step 1 - Run the Windows setup script

Open PowerShell **as Administrator** and run:

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
cd C:\EVMarketResearch
.\infrastructure\scripts\windows_setup.ps1
```

This installs Terraform, doctl, and generates an SSH key at
`~/.ssh/ev_research_ed25519`. The public key is printed at the end - copy it.

---

## Step 2 - Get DigitalOcean credentials

### Personal Access Token (DO_TOKEN)
1. Go to https://cloud.digitalocean.com/account/api/tokens
2. Click **Generate New Token**
3. Name: `ev-research`, Scopes: **Read + Write**
4. Copy the token (shown only once)

### Spaces Access Keys (DO_SPACES_KEY + DO_SPACES_SECRET)
1. Go to https://cloud.digitalocean.com/account/api/spaces
2. Click **Generate New Key**
3. Name: `ev-research`
4. Copy both the key and secret

---

## Step 3 - Fill in terraform.tfvars

```powershell
Copy-Item infrastructure\terraform\terraform.tfvars.example infrastructure\terraform\terraform.tfvars
```

Edit `infrastructure\terraform\terraform.tfvars` and fill in:
- `do_token`
- `spaces_access_key` / `spaces_secret_key`
- `ssh_public_key` (from Step 1 output)
- `spaces_bucket_name` - must be globally unique, e.g. `ev-research-yourname-2025`

---

## Step 4 - Authenticate doctl

```powershell
doctl auth init
# Paste your DO_TOKEN when prompted
doctl account get   # confirm it works
```

---

## Step 5 - Apply Terraform

```powershell
cd infrastructure\terraform
terraform init
terraform plan      # review what will be created
terraform apply     # type "yes" to confirm
```

This creates:
- 1× Droplet (`s-2vcpu-4gb`, ~$24/mo)
- 1× Managed Postgres (`db-s-1vcpu-1gb`, ~$15/mo)
- 1× Spaces bucket (pay-per-use, ~$5/mo minimum)

**Save the outputs** - you'll need `droplet_ip` and `db_uri`.

To retrieve outputs later:
```powershell
terraform output droplet_ip
terraform output db_uri   # sensitive - use -raw flag
terraform output -raw db_uri
```

---

## Step 6 - Fill in config/.env

```powershell
Copy-Item config\.env.example config\.env
```

Edit `config\.env`:
- Fill in `DROPLET_IP` from terraform output
- Fill in `DB_HOST`, `DB_PORT`, `DB_PASSWORD`, `DATABASE_URL` from terraform output
- Fill in all API keys as you obtain them (see CLAUDE.md for where to get each)

---

## Step 7 - Enable pgvector on Postgres

SSH into the Droplet:
```powershell
ssh -i $env:USERPROFILE\.ssh\ev_research_ed25519 root@<DROPLET_IP>
```

Then connect to Postgres and enable the extension:
```bash
psql "postgresql://pipeline:PASSWORD@HOST:25060/ev_research?sslmode=require"
```
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_chunks (
    id            BIGSERIAL PRIMARY KEY,
    source        TEXT NOT NULL,
    app_name      TEXT NOT NULL,
    content       TEXT NOT NULL,
    metadata      JSONB DEFAULT '{}',
    embedding     vector(1536),
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx
    ON document_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

---

## Step 8 - Verify bootstrap completed on Droplet

```bash
# SSH in, then:
cat /var/log/bootstrap.log | tail -5
# Should end with: "=== Bootstrap complete at ..."
```

---

## What's next

Once infra is up and .env is filled in, return to Claude Code and say
**"infra is ready, let's build the scrapers"**.
