#!/bin/bash
# WSL-specific deployment script for NCLE Web Application
# Since WSL doesn't fully support systemd, this uses a simpler approach

set -e  # Exit on error

echo "================================"
echo "NCLE Web WSL Deployment Script"
echo "================================"

PROJECT_DIR="/home/ianms/git_repos/NCLEweb"
DOMAIN="localhost"  # For local testing

echo ""
echo "Step 1: Installing dependencies..."
sudo apt-get update
sudo apt-get install -y nginx

echo ""
echo "Step 2: Creating logs directory..."
mkdir -p $PROJECT_DIR/logs
touch $PROJECT_DIR/logs/access.log
touch $PROJECT_DIR/logs/error.log

echo ""
echo "Step 3: Installing Gunicorn in virtual environment..."
cd $PROJECT_DIR
source venv/bin/activate
pip install gunicorn
deactivate

echo ""
echo "Step 4: Creating WSL-compatible Nginx configuration..."
cat > /tmp/nclweb_nginx.conf << 'EOF'
# NCLE Web - WSL/Local Development Configuration

upstream nclweb_backend {
    server 127.0.0.1:8000;
    keepalive 64;
}

# Rate limiting zone
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/m;

server {
    listen 80;
    server_name localhost;
    
    client_max_body_size 60M;
    
    root /home/ianms/git_repos/NCLEweb;
    index index.html;
    
    # Serve static files
    location / {
        try_files $uri $uri/ =404;
    }
    
    # Proxy API requests
    location /api/ {
        limit_req zone=api_limit burst=5 nodelay;
        limit_req_status 429;
        
        proxy_pass http://nclweb_backend;
        proxy_http_version 1.1;
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        
        proxy_buffering off;
        proxy_request_buffering off;
    }
    
    # Serve data files
    location /data/ {
        alias /home/ianms/git_repos/NCLEweb/data/;
        
        location ~ \.(php|py|sh|pl)$ {
            deny all;
        }
        
        location ~ \.json$ {
            add_header Access-Control-Allow-Origin *;
            add_header Access-Control-Allow-Methods "GET, OPTIONS";
            add_header Access-Control-Allow-Headers "Content-Type";
        }
    }
    
    access_log /home/ianms/git_repos/NCLEweb/logs/nginx_access.log;
    error_log /home/ianms/git_repos/NCLEweb/logs/nginx_error.log;
}
EOF

echo ""
echo "Step 5: Installing Nginx configuration..."
sudo cp /tmp/nclweb_nginx.conf /etc/nginx/sites-available/nclweb
sudo ln -sf /etc/nginx/sites-available/nclweb /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

echo ""
echo "Step 6: Testing Nginx configuration..."
sudo nginx -t

echo ""
echo "Step 7: Restarting Nginx..."
sudo service nginx restart

echo ""
echo "Step 8: Creating start script..."
cat > $PROJECT_DIR/start_server.sh << 'EOF'
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
EOF

chmod +x $PROJECT_DIR/start_server.sh

echo ""
echo "================================"
echo "WSL Deployment Complete!"
echo "================================"
echo ""
echo "To start the server:"
echo "  cd $PROJECT_DIR"
echo "  ./start_server.sh"
echo ""
echo "Or run in background:"
echo "  nohup ./start_server.sh > /dev/null 2>&1 &"
echo ""
echo "Access the application:"
echo "  http://localhost (via Nginx)"
echo "  http://localhost:8000 (direct backend access)"
echo ""
echo "To stop the backend:"
echo "  pkill -f 'gunicorn.*backend:app'"
echo ""
echo "View logs:"
echo "  Backend: tail -f logs/access.log logs/error.log"
echo "  Nginx: tail -f logs/nginx_access.log logs/nginx_error.log"
echo ""
