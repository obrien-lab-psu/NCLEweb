#!/bin/bash
# Start NCLE Web Application

cd /home/ianms/git_repos/NCLEweb

# Use base conda environment (required for EntDetect 1.1.1 compatibility)
eval "$(/home/ianms/miniconda3/bin/conda shell.bash hook)"
conda activate base

echo "Starting NCLE Web backend on port 8000 with base conda environment..."
/home/ianms/miniconda3/bin/python -m gunicorn -w 4 \
    -k uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 \
    --timeout 300 \
    --access-logfile logs/access.log \
    --error-logfile logs/error.log \
    --log-level info \
    py.backend:app
