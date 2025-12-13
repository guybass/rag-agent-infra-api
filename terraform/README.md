# RAG Agent Infrastructure - Automated Deployment

Fully automated EC2 + S3 deployment. Run from any machine with AWS credentials (or an EC2 with admin IAM role).

## Architecture

```
┌─────────────────────────────────────────┐
│              EC2 Instance               │
│            (Ubuntu 24.04)               │
│             (t3.medium)                 │
│                                         │
│  ┌─────────────┐  ┌─────────────────┐   │
│  │  RAG API    │  │     Redis       │   │
│  │  (FastAPI)  │  │   (Sessions)    │   │
│  │  Port 8000  │  │   Port 6379     │   │
│  └─────────────┘  └─────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │  /opt/rag-agent/data/           │    │
│  │  ├── chromadb/   (Vector DB)    │    │
│  │  └── terraform/  (TF files)     │    │
│  └─────────────────────────────────┘    │
│                                         │
└─────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│           S3 Bucket                     │
│    (Backups, Terraform state files)     │
└─────────────────────────────────────────┘
```

## Cost

~$30-40/month total:
- EC2 t3.medium: ~$30/month
- S3: ~$1/month
- Elastic IP: Free (when attached)

## Deploy from Agent Machine (EC2 with Admin Role)

If running from an EC2 with admin IAM role, no credentials are needed:

```bash
# Clone the repo (if not already done)
git clone https://github.com/guybass/rag-agent-infra-api.git
cd rag-agent-infra-api/terraform

# Initialize Terraform
terraform init

# Deploy (no tfvars needed - uses defaults)
terraform apply
```

## Deploy from Local Machine

```bash
# 1. Configure AWS credentials
aws configure

# 2. Clone and enter terraform directory
git clone https://github.com/guybass/rag-agent-infra-api.git
cd rag-agent-infra-api/terraform

# 3. Copy and edit variables (optional)
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars if you want to customize

# 4. Deploy
terraform init
terraform apply
```

## Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `aws_region` | us-east-1 | AWS region |
| `project_name` | rag-agent | Resource naming prefix |
| `instance_type` | t3.medium | EC2 instance type |
| `key_name` | "" | SSH key (empty = SSM-only) |
| `github_repo_url` | guybass/rag-agent-infra-api | Repo to clone |
| `github_branch` | main | Branch to deploy |

## Outputs

After `terraform apply`, you'll see:

```
api_url          = "http://<IP>:8000"
health_check_url = "http://<IP>:8000/health"
api_docs_url     = "http://<IP>:8000/docs"
ssm_connect      = "aws ssm start-session --target i-xxxxx"
```

## Connect to Instance

**Via SSM (recommended - no SSH key needed):**
```bash
aws ssm start-session --target <instance-id>
```

**Via SSH (if key_name was set):**
```bash
ssh -i ~/.ssh/your-key.pem ubuntu@<public-ip>
```

## Verify Deployment

The instance auto-deploys on boot. Check status:

```bash
# View setup log
cat /var/log/user-data.log

# Check service status
sudo systemctl status rag-agent

# View service logs
sudo journalctl -u rag-agent -f

# Test health endpoint
curl http://localhost:8000/health
```

## Useful Commands

```bash
# Restart service
sudo systemctl restart rag-agent

# Check Redis
redis-cli ping

# Update code
cd ~/rag-agent-infra-api
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart rag-agent

# Backup ChromaDB to S3
aws s3 sync /opt/rag-agent/data/chromadb s3://YOUR_BUCKET/backups/chromadb/
```

## Destroy

```bash
terraform destroy
```
