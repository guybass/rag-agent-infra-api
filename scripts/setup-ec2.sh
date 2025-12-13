#!/bin/bash
set -e

# EC2 Initial Setup Script for RAG Agent Infrastructure API
# Run this script after launching a new EC2 instance

echo "=== EC2 Initial Setup for RAG Agent API ==="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./setup-ec2.sh)"
    exit 1
fi

# Update system
echo "Step 1: Updating system packages..."
apt-get update && apt-get upgrade -y

# Install essential tools
echo "Step 2: Installing essential tools..."
apt-get install -y \
    git \
    curl \
    wget \
    unzip \
    htop \
    vim \
    jq

# Install Docker
echo "Step 3: Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    systemctl enable docker
    systemctl start docker
    rm get-docker.sh

    # Add ubuntu user to docker group
    usermod -aG docker ubuntu || true
fi

# Install Docker Compose
echo "Step 4: Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# Install AWS CLI
echo "Step 5: Installing AWS CLI..."
if ! command -v aws &> /dev/null; then
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip awscliv2.zip
    ./aws/install
    rm -rf aws awscliv2.zip
fi

# Configure firewall
echo "Step 6: Configuring firewall..."
if command -v ufw &> /dev/null; then
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow 8000/tcp
    ufw --force enable
fi

# Create app directory
echo "Step 7: Creating application directory..."
mkdir -p /opt/rag-agent-api
chown ubuntu:ubuntu /opt/rag-agent-api

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Clone your repository:"
echo "   cd /opt/rag-agent-api"
echo "   git clone <your-repo-url> ."
echo ""
echo "2. Configure environment:"
echo "   cp .env.example .env"
echo "   nano .env"
echo ""
echo "3. Deploy the application:"
echo "   sudo ./scripts/deploy.sh"
echo ""
echo "Note: You may need to log out and back in for docker group changes to take effect."
