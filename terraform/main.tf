# =============================================================================
# RAG Agent Infrastructure - Simple EC2 + S3 Deployment
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
  default = "us-east-1"
}

variable "project_name" {
  default = "rag-agent"
}

variable "instance_type" {
  default = "t3.medium"  # 2 vCPU, 4GB RAM - good for ChromaDB
}

variable "key_name" {
  description = "SSH key pair name"
  type        = string
}

variable "allowed_ssh_cidr" {
  description = "CIDR block allowed to SSH (your IP)"
  default     = "0.0.0.0/0"  # Restrict this to your IP!
}

# =============================================================================
# Data Sources
# =============================================================================

# Latest Amazon Linux 2023 AMI
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
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

  # SSH
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  # API
  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTP (optional - for nginx reverse proxy)
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTPS (optional)
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Redis (internal only - localhost)
  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    self        = true
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

# =============================================================================
# EC2 Instance
# =============================================================================

resource "aws_instance" "app" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = var.instance_type
  key_name               = var.key_name
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

    # Update system
    dnf update -y

    # Install dependencies
    dnf install -y docker git python3.11 python3.11-pip redis6

    # Start Docker
    systemctl start docker
    systemctl enable docker
    usermod -aG docker ec2-user

    # Start Redis
    systemctl start redis6
    systemctl enable redis6

    # Create app directory
    mkdir -p /opt/rag-agent
    chown ec2-user:ec2-user /opt/rag-agent

    # Create data directories
    mkdir -p /opt/rag-agent/data/chromadb
    mkdir -p /opt/rag-agent/data/terraform
    chown -R ec2-user:ec2-user /opt/rag-agent/data

    # Create systemd service
    cat > /etc/systemd/system/rag-agent.service << 'SERVICEEOF'
    [Unit]
    Description=RAG Agent Infrastructure API
    After=network.target redis6.service

    [Service]
    Type=simple
    User=ec2-user
    WorkingDirectory=/opt/rag-agent/app
    ExecStart=/usr/bin/python3.11 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
    Restart=always
    RestartSec=5
    Environment=CHROMA_PERSIST_DIRECTORY=/opt/rag-agent/data/chromadb
    Environment=TERRAFORM_STORAGE_PATH=/opt/rag-agent/data/terraform
    Environment=REDIS_URL=redis://localhost:6379/0
    Environment=AWS_REGION=${var.aws_region}

    [Install]
    WantedBy=multi-user.target
    SERVICEEOF

    systemctl daemon-reload

    echo "Setup complete! Clone your repo to /opt/rag-agent/app and start the service."
  EOF

  tags = {
    Name = "${var.project_name}-server"
  }
}

# =============================================================================
# Elastic IP (optional - for stable IP)
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
  value = aws_instance.app.id
}

output "public_ip" {
  value = aws_eip.app.public_ip
}

output "api_url" {
  value = "http://${aws_eip.app.public_ip}:8000"
}

output "ssh_command" {
  value = "ssh -i ~/.ssh/${var.key_name}.pem ec2-user@${aws_eip.app.public_ip}"
}

output "s3_bucket" {
  value = aws_s3_bucket.data.id
}

output "setup_commands" {
  value = <<-EOT

    # 1. SSH into the instance
    ssh -i ~/.ssh/${var.key_name}.pem ec2-user@${aws_eip.app.public_ip}

    # 2. Clone your repo
    cd /opt/rag-agent
    git clone <your-repo-url> app

    # 3. Install dependencies
    cd app
    pip3.11 install -r requirements.txt

    # 4. Create .env file
    cat > .env << 'ENV'
    APP_NAME=RAG Agent Infrastructure API
    DEBUG=false
    HOST=0.0.0.0
    PORT=8000
    AWS_REGION=${var.aws_region}
    REDIS_URL=redis://localhost:6379/0
    CHROMA_PERSIST_DIRECTORY=/opt/rag-agent/data/chromadb
    TERRAFORM_STORAGE_PATH=/opt/rag-agent/data/terraform
    ENV

    # 5. Start the service
    sudo systemctl start rag-agent
    sudo systemctl enable rag-agent

    # 6. Check status
    sudo systemctl status rag-agent

    # 7. View logs
    sudo journalctl -u rag-agent -f

  EOT
}
