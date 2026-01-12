#!/bin/bash
# Start NCLE Web Application

cd /home/ianms/git_repos/NCLEweb
source venv/bin/activate

echo "Starting NCLE Web backend on port 8000..."
gunicorn -w 4 \
    -k uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 \
    --timeout 300 \
    --access-logfile logs/access.log \
    --error-logfile logs/error.log \
    --log-level info \
    py.backend:app
