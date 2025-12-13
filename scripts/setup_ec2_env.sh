#!/bin/bash
# Setup script for RAG Agent Infrastructure API on EC2
# This script creates the .env file and restarts the service

set -e

# Configuration
APP_DIR="/home/ubuntu/rag-agent-infra-api"
ENV_FILE="${APP_DIR}/.env"

echo "=========================================="
echo "RAG Agent Infrastructure API - EC2 Setup"
echo "=========================================="

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo "Please run with sudo: sudo bash $0"
    exit 1
fi

# Navigate to app directory
cd "$APP_DIR" || { echo "Directory $APP_DIR not found!"; exit 1; }

# Pull latest changes
echo ""
echo "[1/4] Pulling latest changes from git..."
sudo -u ubuntu git pull

# Create .env file
echo ""
echo "[2/4] Creating .env file..."
cat > "$ENV_FILE" << 'EOF'
# ===========================================
# RAG Agent Infrastructure API Configuration
# ===========================================

# Authentication - DISABLED for private VPC testing
AUTH_DISABLED=true

# LLM Provider
LLM_PROVIDER=bedrock

# AWS Bedrock - Claude 4.5 Sonnet (CRIS)
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0

# AWS Authentication: Uses EC2 IAM Role (no credentials needed)
# If you need to assume a different role, uncomment:
# AWS_ASSUME_ROLE_ARN=arn:aws:iam::123456789012:role/YourRole

# Redis
REDIS_URL=redis://localhost:6379/0

# ChromaDB
CHROMA_PERSIST_DIRECTORY=./chroma_data

# Terraform Storage
TERRAFORM_STORAGE_PATH=./terraform_data
EOF

# Set proper ownership
chown ubuntu:ubuntu "$ENV_FILE"
chmod 600 "$ENV_FILE"

echo "   Created: $ENV_FILE"

# Restart the service
echo ""
echo "[3/4] Restarting rag-agent service..."
systemctl restart rag-agent
sleep 2

# Check service status
echo ""
echo "[4/4] Checking service status..."
if systemctl is-active --quiet rag-agent; then
    echo "   ✓ Service is running"
else
    echo "   ✗ Service failed to start!"
    systemctl status rag-agent --no-pager
    exit 1
fi

# Test the API
echo ""
echo "=========================================="
echo "Testing API..."
echo "=========================================="

# Health check
echo ""
echo "Health check:"
curl -s http://localhost:8000/health | python3 -m json.tool

# Test chat endpoint (no auth needed)
echo ""
echo ""
echo "Chat test (Claude 4.5 Sonnet):"
curl -s -X POST "http://localhost:8000/api/v1/chat/" \
  -H "Content-Type: application/json" \
  -d '{"query": "What model are you? Reply in one short sentence."}' | python3 -m json.tool

echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "API is ready at: http://localhost:8000"
echo "Swagger docs at: http://localhost:8000/docs"
echo ""
