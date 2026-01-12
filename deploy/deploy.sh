#!/bin/bash
# Deployment script for NCLE Web Application
# This script sets up the production environment

set -e  # Exit on error

echo "================================"
echo "NCLE Web Deployment Script"
echo "================================"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (sudo ./deploy.sh)"
    exit 1
fi

# Configuration
PROJECT_DIR="/home/ianms/git_repos/NCLEweb"
DOMAIN="ncleweb.org"
EMAIL="nclewebnotifications@gmail.com"  # For Let's Encrypt notifications

echo ""
echo "Step 1: Installing dependencies..."
apt-get update
apt-get install -y nginx certbot python3-certbot-nginx ufw

echo ""
echo "Step 2: Setting up firewall..."
ufw allow 'Nginx Full'
ufw allow OpenSSH
echo "Firewall rules added. Run 'ufw enable' to activate (will ask for confirmation)"

echo ""
echo "Step 3: Creating logs directory..."
mkdir -p $PROJECT_DIR/logs
chown ianms:ianms $PROJECT_DIR/logs

echo ""
echo "Step 4: Installing Gunicorn in virtual environment..."
cd $PROJECT_DIR
source venv/bin/activate
pip install gunicorn
deactivate

echo ""
echo "Step 5: Copying Nginx configuration..."
cp $PROJECT_DIR/deploy/nginx.conf /etc/nginx/sites-available/nclweb

# Update domain in nginx config
sed -i "s/your_domain.com/$DOMAIN/g" /etc/nginx/sites-available/nclweb

# Enable site
ln -sf /etc/nginx/sites-available/nclweb /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

echo ""
echo "Step 6: Testing Nginx configuration..."
nginx -t

echo ""
echo "Step 7: Restarting Nginx..."
systemctl restart nginx

echo ""
echo "Step 8: Setting up systemd service..."
cp $PROJECT_DIR/deploy/nclweb.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable nclweb
systemctl start nclweb

echo ""
echo "Step 9: Checking service status..."
systemctl status nclweb --no-pager

echo ""
echo "================================"
echo "Deployment Complete!"
echo "================================"
echo ""
echo "Next steps:"
echo "1. Ensure your domain ($DOMAIN) points to this server's IP"
echo "2. Run: sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN"
echo "3. Enable firewall: sudo ufw enable"
echo "4. Check service: sudo systemctl status nclweb"
echo "5. View logs: sudo journalctl -u nclweb -f"
echo ""
echo "Service management commands:"
echo "  Start:   sudo systemctl start nclweb"
echo "  Stop:    sudo systemctl stop nclweb"
echo "  Restart: sudo systemctl restart nclweb"
echo "  Status:  sudo systemctl status nclweb"
echo "  Logs:    sudo journalctl -u nclweb -f"
echo ""
