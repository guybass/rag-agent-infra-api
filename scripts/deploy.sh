#!/bin/bash
set -e

# RAG Agent Infrastructure API - EC2 Deployment Script

echo "=== RAG Agent Infrastructure API Deployment ==="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./deploy.sh)"
    exit 1
fi

# Update system
echo "Updating system packages..."
apt-get update && apt-get upgrade -y

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    systemctl enable docker
    systemctl start docker
    rm get-docker.sh
fi

# Install Docker Compose if not present
if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo ""
    echo "IMPORTANT: Please edit .env file with your actual credentials!"
    echo "Run: nano .env"
    echo ""
fi

# Build and start the application
echo "Building and starting the application..."
docker-compose down --remove-orphans || true
docker-compose build --no-cache
docker-compose up -d

# Wait for health check
echo "Waiting for application to be healthy..."
sleep 10

# Check if running
if docker-compose ps | grep -q "Up"; then
    echo ""
    echo "=== Deployment Successful ==="
    echo "API is running at: http://$(curl -s ifconfig.me):8000"
    echo "API Documentation: http://$(curl -s ifconfig.me):8000/docs"
    echo ""
    echo "To view logs: docker-compose logs -f"
    echo "To stop: docker-compose down"
else
    echo "Deployment failed. Check logs with: docker-compose logs"
    exit 1
fi
