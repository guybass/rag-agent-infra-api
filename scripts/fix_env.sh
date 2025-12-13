#!/bin/bash
# Fix .env file and restart service
# Run from anywhere - automatically finds the project directory

set -e

# Find the script's directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "Fixing .env and restarting service"
echo "=========================================="
echo "Project directory: $PROJECT_DIR"

# Create .env in project directory
echo ""
echo "[1/5] Creating .env file..."
cat > "${PROJECT_DIR}/.env" << 'EOF'
# ===========================================
# RAG Agent Infrastructure API Configuration
# ===========================================

# Application
APP_NAME=RAG Agent Infrastructure API
APP_ENV=production
DEBUG=false
HOST=0.0.0.0
PORT=8000

# AUTHENTICATION DISABLED FOR PRIVATE VPC TESTING
AUTH_DISABLED=true

# AWS (uses EC2 instance role by default)
AWS_REGION=us-east-1

# Redis
REDIS_URL=redis://localhost:6379/0

# Storage Paths
CHROMA_PERSIST_DIRECTORY=./chroma_data
TERRAFORM_STORAGE_PATH=./terraform_data

# LLM Provider - Claude 4.5 Sonnet (CRIS - Cross Region Inference)
LLM_PROVIDER=bedrock
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
EOF

chmod 644 "${PROJECT_DIR}/.env"
echo "   ✓ Created: ${PROJECT_DIR}/.env"

# Verify content
echo ""
echo "[2/5] Verifying .env content..."
if grep -q "AUTH_DISABLED=true" "${PROJECT_DIR}/.env"; then
    echo "   ✓ AUTH_DISABLED=true is set"
else
    echo "   ✗ AUTH_DISABLED not found!"
    exit 1
fi

if grep -q "us.anthropic.claude-sonnet-4-5" "${PROJECT_DIR}/.env"; then
    echo "   ✓ Claude 4.5 Sonnet model configured"
else
    echo "   ✗ Wrong model ID!"
    exit 1
fi

# Kill any stray processes
echo ""
echo "[3/5] Killing stray Python/uvicorn processes..."
sudo pkill -9 -f uvicorn 2>/dev/null || true
sudo pkill -9 -f "python.*app.main" 2>/dev/null || true
sudo pkill -9 -f "python.*main:app" 2>/dev/null || true
sleep 1
echo "   ✓ Processes killed"

# Clear Python cache
echo ""
echo "[4/5] Clearing Python cache..."
find "${PROJECT_DIR}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "${PROJECT_DIR}" -type f -name "*.pyc" -delete 2>/dev/null || true
echo "   ✓ Cache cleared"

# Restart service
echo ""
echo "[5/5] Restarting rag-agent service..."
sudo systemctl restart rag-agent
sleep 3

# Check if service is running
if sudo systemctl is-active --quiet rag-agent; then
    echo "   ✓ Service is running"
else
    echo "   ✗ Service failed!"
    sudo journalctl -u rag-agent --no-pager -n 20
    exit 1
fi

# Wait for API
echo ""
echo "Waiting for API..."
for i in {1..10}; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        echo "   ✓ API is responding"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "   ✗ API not responding!"
        sudo journalctl -u rag-agent --no-pager -n 20
        exit 1
    fi
    sleep 1
    echo "   Waiting... ($i/10)"
done

# Test endpoints
echo ""
echo "=========================================="
echo "Testing API..."
echo "=========================================="

echo ""
echo "Health check:"
curl -s http://localhost:8000/health | python3 -m json.tool

echo ""
echo "Sessions (should work without auth):"
RESPONSE=$(curl -s http://localhost:8000/api/v1/sessions/)
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

if echo "$RESPONSE" | grep -q "Authentication required"; then
    echo ""
    echo "   ✗ AUTH STILL REQUIRED - checking service logs..."
    sudo journalctl -u rag-agent --no-pager -n 10
else
    echo ""
    echo "   ✓ AUTH DISABLED WORKING!"
fi

echo ""
echo "=========================================="
echo "Done!"
echo "=========================================="
