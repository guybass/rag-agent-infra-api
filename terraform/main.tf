# =============================================================================
# RAG Agent Infrastructure - Fully Automated EC2 + S3 Deployment
# =============================================================================
# Run this from an EC2 with admin IAM role - no credentials needed
# =============================================================================

terraform {
  required_version = ">= 1.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# =============================================================================
# Variables
# =============================================================================

variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "rag-agent"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.medium"  # 2 vCPU, 4GB RAM - good for ChromaDB
}

variable "key_name" {
  description = "SSH key pair name (optional - leave empty for SSM-only access)"
  type        = string
  default     = ""
}

variable "allowed_ssh_cidr" {
  description = "CIDR block allowed to SSH (your IP)"
  type        = string
  default     = "0.0.0.0/0"  # Restrict this to your IP!
}

variable "github_repo_url" {
  description = "GitHub repository URL for the RAG Agent API"
  type        = string
  default     = "https://github.com/guybass/rag-agent-infra-api.git"
}

variable "github_branch" {
  description = "Git branch to deploy"
  type        = string
  default     = "main"
}

# =============================================================================
# Data Sources
# =============================================================================

# Latest Ubuntu 24.04 LTS AMI
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]  # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# =============================================================================
# S3 Bucket for Terraform Files & Backups
# =============================================================================

resource "aws_s3_bucket" "data" {
  bucket = "${var.project_name}-data-${random_id.bucket_suffix.hex}"

  tags = {
    Name = "${var.project_name}-data"
  }
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# =============================================================================
# Security Group
# =============================================================================

resource "aws_security_group" "app" {
  name        = "${var.project_name}-sg"
  description = "Security group for RAG Agent API"
  vpc_id      = data.aws_vpc.default.id

  # SSH (only if key_name provided)
  dynamic "ingress" {
    for_each = var.key_name != "" ? [1] : []
    content {
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = [var.allowed_ssh_cidr]
    }
  }

  # API
  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTP (for nginx reverse proxy)
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTPS
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-sg"
  }
}

# =============================================================================
# IAM Role for EC2
# =============================================================================

resource "aws_iam_role" "ec2" {
  name = "${var.project_name}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_instance_profile" "ec2" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.ec2.name
}

# S3 Access
resource "aws_iam_role_policy" "s3_access" {
  name = "s3-access"
  role = aws_iam_role.ec2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.data.arn,
          "${aws_s3_bucket.data.arn}/*"
        ]
      }
    ]
  })
}

# Bedrock Access (for LLM)
resource "aws_iam_role_policy" "bedrock_access" {
  name = "bedrock-access"
  role = aws_iam_role.ec2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = "*"
      }
    ]
  })
}

# AWS Read Access (for live resource fetching)
resource "aws_iam_role_policy" "aws_read" {
  name = "aws-read"
  role = aws_iam_role.ec2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:Describe*",
          "eks:Describe*",
          "eks:List*",
          "rds:Describe*",
          "s3:ListAllMyBuckets",
          "s3:GetBucketLocation",
          "lambda:List*",
          "elasticloadbalancing:Describe*",
          "dynamodb:Describe*",
          "dynamodb:List*",
          "iam:ListRoles",
          "iam:GetRole"
        ]
        Resource = "*"
      }
    ]
  })
}

# SSM Access (for Session Manager)
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# =============================================================================
# EC2 Instance - Fully Automated Deployment
# =============================================================================

resource "aws_instance" "app" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = var.key_name != "" ? var.key_name : null
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  subnet_id              = data.aws_subnets.default.ids[0]

  root_block_device {
    volume_size = 30  # GB
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = <<-EOF
    #!/bin/bash
    set -e
    exec > >(tee /var/log/user-data.log) 2>&1
    echo "=== Starting RAG Agent Setup ==="

    # Update system
    apt-get update -y
    apt-get upgrade -y

    # Install dependencies
    apt-get install -y python3 python3-pip python3-venv redis-server git curl jq

    # Start Redis
    systemctl start redis-server
    systemctl enable redis-server

    # Create data directories
    mkdir -p /opt/rag-agent/data/chromadb
    mkdir -p /opt/rag-agent/data/terraform

    # Clone repository
    cd /home/ubuntu
    git clone -b ${var.github_branch} ${var.github_repo_url} rag-agent-infra-api
    chown -R ubuntu:ubuntu rag-agent-infra-api /opt/rag-agent

    # Setup Python virtual environment
    cd /home/ubuntu/rag-agent-infra-api
    sudo -u ubuntu python3 -m venv venv
    sudo -u ubuntu bash -c "source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt"

    # Create .env file
    cat > /home/ubuntu/rag-agent-infra-api/.env << 'ENVEOF'
    APP_NAME=RAG Agent Infrastructure API
    DEBUG=false
    HOST=0.0.0.0
    PORT=8000
    AWS_REGION=${var.aws_region}
    REDIS_URL=redis://localhost:6379/0
    CHROMA_PERSIST_DIRECTORY=/opt/rag-agent/data/chromadb
    TERRAFORM_STORAGE_PATH=/opt/rag-agent/data/terraform
    LLM_PROVIDER=bedrock
    BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
    ENVEOF
    chown ubuntu:ubuntu /home/ubuntu/rag-agent-infra-api/.env

    # Create systemd service
    cat > /etc/systemd/system/rag-agent.service << 'SVCEOF'
    [Unit]
    Description=RAG Agent Infrastructure API
    After=network.target redis-server.service
    Requires=redis-server.service

    [Service]
    Type=simple
    User=ubuntu
    Group=ubuntu
    WorkingDirectory=/home/ubuntu/rag-agent-infra-api
    Environment="PATH=/home/ubuntu/rag-agent-infra-api/venv/bin:/usr/local/bin:/usr/bin:/bin"
    EnvironmentFile=/home/ubuntu/rag-agent-infra-api/.env
    ExecStart=/home/ubuntu/rag-agent-infra-api/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
    Restart=always
    RestartSec=5

    [Install]
    WantedBy=multi-user.target
    SVCEOF

    # Start service
    systemctl daemon-reload
    systemctl enable rag-agent
    systemctl start rag-agent

    echo "=== RAG Agent Setup Complete ==="
    echo "Service status:"
    systemctl status rag-agent --no-pager || true
  EOF

  tags = {
    Name = "${var.project_name}-server"
  }
}

# =============================================================================
# Elastic IP (for stable IP)
# =============================================================================

resource "aws_eip" "app" {
  instance = aws_instance.app.id
  domain   = "vpc"

  tags = {
    Name = "${var.project_name}-eip"
  }
}

# =============================================================================
# Outputs
# =============================================================================

output "instance_id" {
  description = "EC2 Instance ID"
  value       = aws_instance.app.id
}

output "public_ip" {
  description = "Public IP address"
  value       = aws_eip.app.public_ip
}

output "api_url" {
  description = "API base URL"
  value       = "http://${aws_eip.app.public_ip}:8000"
}

output "health_check_url" {
  description = "Health check endpoint"
  value       = "http://${aws_eip.app.public_ip}:8000/health"
}

output "api_docs_url" {
  description = "API documentation (Swagger)"
  value       = "http://${aws_eip.app.public_ip}:8000/docs"
}

output "s3_bucket" {
  description = "S3 bucket for data storage"
  value       = aws_s3_bucket.data.id
}

output "ssm_connect" {
  description = "Connect via SSM Session Manager"
  value       = "aws ssm start-session --target ${aws_instance.app.id}"
}

output "ssh_command" {
  description = "SSH command (if key_name was provided)"
  value       = var.key_name != "" ? "ssh -i ~/.ssh/${var.key_name}.pem ubuntu@${aws_eip.app.public_ip}" : "SSH disabled - use SSM Session Manager"
}

output "view_logs" {
  description = "Commands to view logs on the instance"
  value       = <<-EOT
    # View user-data setup log:
    cat /var/log/user-data.log

    # View service logs:
    sudo journalctl -u rag-agent -f

    # Check service status:
    sudo systemctl status rag-agent
  EOT
}
