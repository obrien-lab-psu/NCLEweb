#!/bin/bash
# Start NCLE Web Application with ncle_prod conda environment

cd /home/ianms/git_repos/NCLEweb

# Kill any existing backend
pkill -f "uvicorn py.backend:app" 2>/dev/null
pkill -9 -f gunicorn 2>/dev/null

echo "Starting NCLE Web backend on port 8000 with ncle_prod environment..."

# Run gunicorn directly from ncle_prod environment
/home/ianms/miniconda3/envs/ncle_prod/bin/gunicorn \
    -w 4 \
    -k uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 \
    --timeout 300 \
    --access-logfile logs/access.log \
    --error-logfile logs/error.log \
    --log-level info \
    py.backend:app
