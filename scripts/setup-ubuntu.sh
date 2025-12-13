#!/bin/bash
set -e

# =============================================================================
# RAG Agent Infrastructure API - Ubuntu EC2 Setup Script
# =============================================================================
# Run: curl -sSL <raw-github-url> | sudo bash
# Or:  sudo bash scripts/setup-ubuntu.sh
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Detect user (ssm-user or ubuntu)
if [ -n "$SUDO_USER" ]; then
    APP_USER="$SUDO_USER"
elif id "ssm-user" &>/dev/null; then
    APP_USER="ssm-user"
elif id "ubuntu" &>/dev/null; then
    APP_USER="ubuntu"
else
    APP_USER="$USER"
fi

APP_HOME=$(eval echo ~$APP_USER)
REPO_DIR="$APP_HOME/rag-agent-infra-api"
DATA_DIR="/opt/rag-agent/data"

echo "=============================================="
echo "  RAG Agent Infrastructure API Setup (Ubuntu)"
echo "=============================================="
echo "User: $APP_USER"
echo "Home: $APP_HOME"
echo "Repo: $REPO_DIR"
echo "Data: $DATA_DIR"
echo "=============================================="

# Check root
if [ "$EUID" -ne 0 ]; then
    error "Please run as root: sudo bash $0"
fi

# =============================================================================
# Step 1: System Update
# =============================================================================
log "Step 1/7: Updating system packages..."
apt-get update -y
apt-get upgrade -y

# =============================================================================
# Step 2: Install Dependencies
# =============================================================================
log "Step 2/7: Installing dependencies..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    redis-server \
    git \
    curl \
    jq \
    htop

# =============================================================================
# Step 3: Start Redis
# =============================================================================
log "Step 3/7: Configuring Redis..."
systemctl start redis-server
systemctl enable redis-server

# Test Redis
if redis-cli ping | grep -q "PONG"; then
    log "Redis is running"
else
    error "Redis failed to start"
fi

# =============================================================================
# Step 4: Create Data Directories
# =============================================================================
log "Step 4/7: Creating data directories..."
mkdir -p $DATA_DIR/chromadb
mkdir -p $DATA_DIR/terraform
chown -R $APP_USER:$APP_USER /opt/rag-agent

# =============================================================================
# Step 5: Install Python Dependencies
# =============================================================================
log "Step 5/7: Installing Python dependencies..."
if [ -d "$REPO_DIR" ]; then
    cd $REPO_DIR

    # Create virtual environment
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        chown -R $APP_USER:$APP_USER venv
    fi

    # Install requirements
    sudo -u $APP_USER bash -c "source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt"
    log "Python dependencies installed"
else
    warn "Repo not found at $REPO_DIR - skipping pip install"
fi

# =============================================================================
# Step 6: Create .env File
# =============================================================================
log "Step 6/7: Creating environment file..."
if [ -d "$REPO_DIR" ] && [ ! -f "$REPO_DIR/.env" ]; then
    cat > $REPO_DIR/.env << 'EOF'
# RAG Agent Infrastructure API Configuration
APP_NAME=RAG Agent Infrastructure API
DEBUG=false
HOST=0.0.0.0
PORT=8000

# AWS (uses instance role by default)
AWS_REGION=us-east-1

# Redis
REDIS_URL=redis://localhost:6379/0

# Storage Paths
CHROMA_PERSIST_DIRECTORY=/opt/rag-agent/data/chromadb
TERRAFORM_STORAGE_PATH=/opt/rag-agent/data/terraform

# LLM Provider (bedrock uses instance role)
LLM_PROVIDER=bedrock
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
EOF
    chown $APP_USER:$APP_USER $REPO_DIR/.env
    log ".env file created"
else
    warn ".env already exists or repo not found"
fi

# =============================================================================
# Step 7: Create Systemd Service
# =============================================================================
log "Step 7/7: Creating systemd service..."
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
ExecStart=$REPO_DIR/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

# Environment variables
Environment="CHROMA_PERSIST_DIRECTORY=$DATA_DIR/chromadb"
Environment="TERRAFORM_STORAGE_PATH=$DATA_DIR/terraform"
Environment="REDIS_URL=redis://localhost:6379/0"
Environment="AWS_REGION=us-east-1"
Environment="LLM_PROVIDER=bedrock"

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

# =============================================================================
# Done
# =============================================================================
echo ""
echo "=============================================="
echo -e "${GREEN}  Setup Complete!${NC}"
echo "=============================================="
echo ""
echo "Next steps:"
echo ""
echo "  1. Start the service:"
echo "     sudo systemctl start rag-agent"
echo "     sudo systemctl enable rag-agent"
echo ""
echo "  2. Check status:"
echo "     sudo systemctl status rag-agent"
echo ""
echo "  3. View logs:"
echo "     sudo journalctl -u rag-agent -f"
echo ""
echo "  4. Test health:"
echo "     curl http://localhost:8000/health"
echo ""
echo "  5. API docs:"
echo "     http://<your-ec2-ip>:8000/docs"
echo ""
echo "=============================================="
