# RAG Agent Infrastructure - Simple Deployment

Single EC2 instance + S3 bucket. That's it.

## Architecture

```
┌─────────────────────────────────────────┐
│              EC2 Instance               │
│            (t3.medium)                  │
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

## Prerequisites

1. AWS CLI configured
2. Terraform installed
3. SSH key pair in AWS

## Deploy

```bash
# 1. Copy variables
cp terraform.tfvars.example terraform.tfvars

# 2. Edit terraform.tfvars
#    - Set your key_name
#    - Set allowed_ssh_cidr to your IP

# 3. Deploy
terraform init
terraform apply
```

## Setup Application

After `terraform apply`, follow the output instructions:

```bash
# SSH into instance
ssh -i ~/.ssh/your-key.pem ec2-user@<PUBLIC_IP>

# Clone repo
cd /opt/rag-agent
git clone https://github.com/your-repo/rag_aget_infra_api.git app

# Install deps
cd app
pip3.11 install -r requirements.txt

# Create .env (copy from output or create manually)
nano .env

# Start service
sudo systemctl start rag-agent
sudo systemctl enable rag-agent

# Check it's running
curl http://localhost:8000/health
```

## Useful Commands

```bash
# View logs
sudo journalctl -u rag-agent -f

# Restart service
sudo systemctl restart rag-agent

# Check Redis
redis6-cli ping

# Backup ChromaDB to S3
aws s3 sync /opt/rag-agent/data/chromadb s3://YOUR_BUCKET/backups/chromadb/

# Restore from S3
aws s3 sync s3://YOUR_BUCKET/backups/chromadb/ /opt/rag-agent/data/chromadb/
```

## Destroy

```bash
terraform destroy
```
