#!/bin/bash
# Setup script for RAG Agent Infrastructure API on EC2
# This script creates the .env file, ensures dependencies, and restarts the service

set -e

# Configuration
APP_DIR="/home/ubuntu/rag-agent-infra-api"
ENV_FILE="${APP_DIR}/.env"
VENV_DIR="${APP_DIR}/venv"

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
echo "[1/8] Pulling latest changes from git..."
sudo -u ubuntu git pull

# Check Redis is running
echo ""
echo "[2/8] Checking Redis..."
if systemctl is-active --quiet redis-server; then
    echo "   ✓ Redis is running"
elif systemctl is-active --quiet redis; then
    echo "   ✓ Redis is running"
else
    echo "   Starting Redis..."
    systemctl start redis-server 2>/dev/null || systemctl start redis 2>/dev/null || {
        echo "   ✗ Redis not installed! Installing..."
        apt-get update && apt-get install -y redis-server
        systemctl enable redis-server
        systemctl start redis-server
    }
fi

# Verify Redis connectivity
if redis-cli ping | grep -q "PONG"; then
    echo "   ✓ Redis responding to ping"
else
    echo "   ✗ Redis not responding!"
    exit 1
fi

# Create required directories
echo ""
echo "[3/8] Creating required directories..."
mkdir -p "${APP_DIR}/chroma_data"
mkdir -p "${APP_DIR}/terraform_data"
chown -R ubuntu:ubuntu "${APP_DIR}/chroma_data" "${APP_DIR}/terraform_data"
chmod 755 "${APP_DIR}/chroma_data" "${APP_DIR}/terraform_data"
echo "   ✓ chroma_data directory ready"
echo "   ✓ terraform_data directory ready"

# Install/update Python dependencies
echo ""
echo "[4/8] Checking Python dependencies..."
if [ -d "$VENV_DIR" ]; then
    source "${VENV_DIR}/bin/activate"
    pip install -q -r requirements.txt
    echo "   ✓ Dependencies installed"
else
    echo "   ✗ Virtual environment not found at $VENV_DIR"
    echo "   Creating virtual environment..."
    sudo -u ubuntu python3 -m venv "$VENV_DIR"
    source "${VENV_DIR}/bin/activate"
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    echo "   ✓ Virtual environment created and dependencies installed"
fi

# Test Python imports
echo ""
echo "[5/8] Testing Python imports..."
source "${VENV_DIR}/bin/activate"
if python3 -c "from app.config import get_settings; print('   ✓ Config OK')" 2>&1; then
    :
else
    echo "   ✗ Config import failed!"
    python3 -c "from app.config import get_settings" 2>&1
    exit 1
fi

# Create .env file
echo ""
echo "[6/8] Creating .env file..."
cat > "$ENV_FILE" << 'EOF'
# ===========================================
# RAG Agent Infrastructure API Configuration
# ===========================================

# Application
APP_ENV=production
DEBUG=false

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

chown ubuntu:ubuntu "$ENV_FILE"
chmod 600 "$ENV_FILE"
echo "   ✓ Created: $ENV_FILE"

# Test full app import (this will catch startup errors)
echo ""
echo "[7/8] Testing application startup..."
cd "$APP_DIR"
source "${VENV_DIR}/bin/activate"

# Test import with timeout
if timeout 30 python3 -c "
import sys
sys.path.insert(0, '.')
from app.main import app
print('   ✓ FastAPI app loads successfully')
" 2>&1; then
    :
else
    echo ""
    echo "   ✗ Application failed to load! Full error:"
    echo "   ----------------------------------------"
    python3 -c "from app.main import app" 2>&1 || true
    echo "   ----------------------------------------"
    echo ""
    echo "   Check the error above and fix before continuing."
    exit 1
fi

# Restart the service
echo ""
echo "[8/8] Restarting rag-agent service..."
systemctl restart rag-agent
sleep 3

# Check service status with logs
echo ""
echo "Checking service status..."
if systemctl is-active --quiet rag-agent; then
    echo "   ✓ Service is running"
else
    echo "   ✗ Service failed to start!"
    echo ""
    echo "   Service status:"
    systemctl status rag-agent --no-pager -l
    echo ""
    echo "   Recent logs:"
    journalctl -u rag-agent --no-pager -n 50
    exit 1
fi

# Wait for app to be ready
echo ""
echo "Waiting for API to be ready..."
for i in {1..10}; do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health | grep -q "200"; then
        echo "   ✓ API is responding"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "   ✗ API not responding after 10 seconds!"
        echo ""
        echo "   Recent logs:"
        journalctl -u rag-agent --no-pager -n 30
        exit 1
    fi
    sleep 1
    echo "   Waiting... ($i/10)"
done

# Test the API
echo ""
echo "=========================================="
echo "Testing API..."
echo "=========================================="

# Health check
echo ""
echo "Health check:"
HEALTH_RESPONSE=$(curl -s http://localhost:8000/health)
echo "$HEALTH_RESPONSE" | python3 -m json.tool || {
    echo "   ✗ Invalid response: $HEALTH_RESPONSE"
    echo ""
    echo "   Recent logs:"
    journalctl -u rag-agent --no-pager -n 30
    exit 1
}

# Test sessions endpoint (no auth needed)
echo ""
echo "Sessions endpoint test:"
curl -s -X GET "http://localhost:8000/api/v1/sessions/" \
  -H "Content-Type: application/json" | python3 -m json.tool || echo "   (may be empty if no sessions)"

# Test chat endpoint (no auth needed) - only if Bedrock is accessible
echo ""
echo "Chat test (Claude 4.5 Sonnet):"
echo "(This may fail if IAM role doesn't have Bedrock access)"
CHAT_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v1/chat/" \
  -H "Content-Type: application/json" \
  -d '{"query": "What model are you? Reply in one short sentence."}')
echo "$CHAT_RESPONSE" | python3 -m json.tool || echo "Response: $CHAT_RESPONSE"

echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "API is ready at: http://localhost:8000"
echo "Swagger docs at: http://localhost:8000/docs"
echo ""
echo "If chat failed, ensure EC2 IAM role has Bedrock permissions."
echo ""
