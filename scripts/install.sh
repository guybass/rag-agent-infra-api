#!/bin/bash
# =============================================================================
# RAG Agent Infrastructure API - One-Command Install
# =============================================================================
# Usage: curl -sSL https://raw.githubusercontent.com/guybass/rag-agent-infra-api/main/scripts/install.sh | sudo bash
# Or:    sudo bash scripts/install.sh
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# =============================================================================
# Configuration
# =============================================================================
REPO_URL="${REPO_URL:-https://github.com/guybass/rag-agent-infra-api.git}"
BRANCH="${BRANCH:-main}"
AWS_REGION="${AWS_REGION:-us-east-1}"

# Detect user
if [ -n "$SUDO_USER" ]; then
    APP_USER="$SUDO_USER"
elif id "ubuntu" &>/dev/null; then
    APP_USER="ubuntu"
elif id "ssm-user" &>/dev/null; then
    APP_USER="ssm-user"
else
    APP_USER="$USER"
fi

APP_HOME=$(eval echo ~$APP_USER)
REPO_DIR="$APP_HOME/rag-agent-infra-api"
DATA_DIR="/opt/rag-agent/data"

echo ""
echo "=============================================="
echo "  RAG Agent Infrastructure API - Installer"
echo "=============================================="
echo "  User:   $APP_USER"
echo "  Repo:   $REPO_DIR"
echo "  Data:   $DATA_DIR"
echo "  Region: $AWS_REGION"
echo "=============================================="
echo ""

# Check root
if [ "$EUID" -ne 0 ]; then
    error "Please run as root: sudo bash $0"
fi

# =============================================================================
# Step 1: Install System Dependencies
# =============================================================================
log "Installing system dependencies..."
apt-get update -y
apt-get install -y python3 python3-pip python3-venv redis-server git curl jq

# =============================================================================
# Step 2: Start Redis
# =============================================================================
log "Starting Redis..."
systemctl start redis-server
systemctl enable redis-server

if redis-cli ping | grep -q "PONG"; then
    log "Redis is running"
else
    error "Redis failed to start"
fi

# =============================================================================
# Step 3: Create Data Directories
# =============================================================================
log "Creating data directories..."
mkdir -p $DATA_DIR/chromadb
mkdir -p $DATA_DIR/terraform
chown -R $APP_USER:$APP_USER /opt/rag-agent

# =============================================================================
# Step 4: Clone or Update Repository
# =============================================================================
if [ -d "$REPO_DIR" ]; then
    log "Updating existing repository..."
    cd $REPO_DIR
    sudo -u $APP_USER git fetch origin
    sudo -u $APP_USER git reset --hard origin/$BRANCH
else
    log "Cloning repository..."
    cd $APP_HOME
    sudo -u $APP_USER git clone -b $BRANCH $REPO_URL rag-agent-infra-api
fi

chown -R $APP_USER:$APP_USER $REPO_DIR

# =============================================================================
# Step 5: Setup Python Virtual Environment
# =============================================================================
log "Setting up Python virtual environment..."
cd $REPO_DIR

if [ ! -d "venv" ]; then
    sudo -u $APP_USER python3 -m venv venv
fi

sudo -u $APP_USER bash -c "source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt"
log "Python dependencies installed"

# =============================================================================
# Step 6: Create Environment File
# =============================================================================
log "Creating environment file..."
cat > $REPO_DIR/.env << EOF
APP_NAME=RAG Agent Infrastructure API
DEBUG=false
HOST=0.0.0.0
PORT=8000
AWS_REGION=$AWS_REGION
REDIS_URL=redis://localhost:6379/0
CHROMA_PERSIST_DIRECTORY=$DATA_DIR/chromadb
TERRAFORM_STORAGE_PATH=$DATA_DIR/terraform
LLM_PROVIDER=bedrock
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
EOF
chown $APP_USER:$APP_USER $REPO_DIR/.env
log ".env file created"

# =============================================================================
# Step 7: Create Systemd Service
# =============================================================================
log "Creating systemd service..."
cat > /etc/systemd/system/rag-agent.service << EOF
[Unit]
Description=RAG Agent Infrastructure API
After=network.target redis-server.service
Requires=redis-server.service

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$REPO_DIR
Environment="PATH=$REPO_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=$REPO_DIR/.env
ExecStart=$REPO_DIR/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

# =============================================================================
# Step 8: Start Service
# =============================================================================
log "Starting RAG Agent service..."
systemctl enable rag-agent
systemctl restart rag-agent

# Wait for service to start
sleep 3

# =============================================================================
# Step 9: Verify
# =============================================================================
if systemctl is-active --quiet rag-agent; then
    log "Service is running"
else
    warn "Service may still be starting. Check: sudo systemctl status rag-agent"
fi

# Test health endpoint
sleep 2
if curl -s http://localhost:8000/health | grep -q "ok\|healthy"; then
    log "Health check passed"
    API_STATUS="running"
else
    warn "Health check pending. Service may still be initializing."
    API_STATUS="starting"
fi

# =============================================================================
# Done
# =============================================================================
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "localhost")

echo ""
echo "=============================================="
echo -e "${GREEN}  Installation Complete!${NC}"
echo "=============================================="
echo ""
echo "  API URL:    http://$PUBLIC_IP:8000"
echo "  API Docs:   http://$PUBLIC_IP:8000/docs"
echo "  Health:     http://$PUBLIC_IP:8000/health"
echo ""
echo "  Useful commands:"
echo "    sudo systemctl status rag-agent"
echo "    sudo journalctl -u rag-agent -f"
echo "    curl http://localhost:8000/health"
echo ""
echo "=============================================="
