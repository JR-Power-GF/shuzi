#!/bin/bash
set -e

DEPLOY_DIR="/opt/training-platform"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Deploying Training Platform ==="

# Backend
echo "[1/5] Installing Python dependencies..."
cd "$REPO_DIR/backend"
source .venv/bin/activate
pip install -r requirements.txt -q

echo "[2/5] Running database migrations..."
alembic upgrade head

# Frontend
echo "[3/5] Building frontend..."
cd "$REPO_DIR/frontend"
npm ci
npm run build

# Deploy
echo "[4/5] Copying files..."
sudo mkdir -p "$DEPLOY_DIR/frontend"
sudo mkdir -p "$DEPLOY_DIR/uploads/tmp"
sudo cp -r "$REPO_DIR/frontend/dist/"* "$DEPLOY_DIR/frontend/dist/"
sudo rsync -av --exclude='.venv' --exclude='__pycache__' "$REPO_DIR/backend/" "$DEPLOY_DIR/backend/"

echo "[5/5] Restarting services..."
sudo cp "$REPO_DIR/deploy/training-platform.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart training-platform
sudo systemctl enable training-platform

# Cron for file cleanup
echo "Setting up daily cleanup cron..."
(crontab -l 2>/dev/null; echo "0 3 * * * cd $DEPLOY_DIR/backend && .venv/bin/python -c 'import asyncio; from app.database import async_session_maker; from app.services.file_cleanup import cleanup_orphan_files; asyncio.run(cleanup_orphan_files(async_session_maker()))'") | crontab -

echo "=== Deployment complete ==="
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost (via Nginx)"
