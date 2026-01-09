#!/bin/bash
# Start the NCLE backend with email notifications enabled
# 
# Usage:
#   1. Copy .env.example to .env
#   2. Edit .env with your SMTP credentials
#   3. Run: ./start_backend.sh

cd "$(dirname "$0")"

# Load environment variables from .env if it exists
if [ -f .env ]; then
    echo "Loading SMTP configuration from .env..."
    export $(grep -v '^#' .env | xargs)
    echo "✓ SMTP_HOST: ${SMTP_HOST}"
    echo "✓ SMTP_USER: ${SMTP_USER}"
    echo "✓ FROM_EMAIL: ${FROM_EMAIL}"
else
    echo "⚠ Warning: .env file not found. Email notifications will be disabled."
    echo "To enable emails:"
    echo "  1. cp .env.example .env"
    echo "  2. Edit .env with your SMTP credentials"
    echo "  3. Run this script again"
    echo ""
fi

# Activate virtual environment
source venv/bin/activate

# Kill any existing backend
pkill -f "uvicorn py.backend:app" 2>/dev/null

# Start backend
echo "Starting backend on port 8000..."
uvicorn py.backend:app --host 0.0.0.0 --port 8000 --reload
