# NCLE Web Deployment Guide

This directory contains deployment configurations for the NCLE Web Application.

## Contents

- `nginx.conf` - Nginx reverse proxy configuration (production with SSL)
- `nclweb.service` - Systemd service file (Linux production servers)
- `deploy.sh` - Full production deployment script (requires domain & SSL)
- `deploy_wsl.sh` - **WSL/local deployment script** (recommended for WSL)

## Quick Start (WSL)

For WSL development/testing:

```bash
cd /home/ianms/git_repos/NCLEweb
chmod +x deploy/deploy_wsl.sh
./deploy/deploy_wsl.sh
```

Then start the server:
```bash
./start_server.sh
```

Access at: http://localhost

## Production Deployment (Linux Server)

### Prerequisites

1. Ubuntu/Debian Linux server
2. Domain name pointing to server IP
3. Root/sudo access
4. Git repository cloned

### Steps

1. **Edit configuration:**
   ```bash
   # Edit deploy/deploy.sh
   DOMAIN="your_domain.com"
   EMAIL="your_email@example.com"
   ```

2. **Run deployment:**
   ```bash
   cd /home/ianms/git_repos/NCLEweb
   chmod +x deploy/deploy.sh
   sudo ./deploy.sh
   ```

3. **Set up SSL certificate:**
   ```bash
   sudo certbot --nginx -d your_domain.com -d www.your_domain.com
   ```

4. **Enable firewall:**
   ```bash
   sudo ufw enable
   ```

## Service Management

### Systemd (Production Linux)

```bash
# Start service
sudo systemctl start nclweb

# Stop service
sudo systemctl stop nclweb

# Restart service
sudo systemctl restart nclweb

# Check status
sudo systemctl status nclweb

# View logs
sudo journalctl -u nclweb -f
```

### Manual (WSL)

```bash
# Start
cd /home/ianms/git_repos/NCLEweb
./start_server.sh

# Or run in background
nohup ./start_server.sh > /dev/null 2>&1 &

# Stop
pkill -f 'gunicorn.*backend:app'

# View logs
tail -f logs/access.log logs/error.log
```

## Security Features

### Rate Limiting
- API endpoints: 10 requests/minute per IP
- Burst allowance: 5 extra requests
- Returns HTTP 429 when exceeded

### SSL/HTTPS (Production)
- Automatic HTTP to HTTPS redirect
- Modern TLS protocols (1.2, 1.3)
- Strong cipher suites
- HSTS header enabled

### Security Headers
- X-Frame-Options: SAMEORIGIN
- X-Content-Type-Options: nosniff
- X-XSS-Protection: enabled
- Strict-Transport-Security: 1 year

### File Upload Protection
- Max upload: 60MB
- File type validation in backend
- Unique job IDs prevent conflicts
- Script execution blocked in data directory

### Firewall (Production)
```bash
# Check status
sudo ufw status

# Allow specific ports
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 22/tcp    # SSH
```

## Monitoring

### Check Backend Health
```bash
curl http://localhost:8000/api/health
```

### View Logs
```bash
# Backend logs
tail -f logs/access.log
tail -f logs/error.log

# Nginx logs (production)
sudo tail -f /var/log/nginx/nclweb_access.log
sudo tail -f /var/log/nginx/nclweb_error.log

# Systemd logs (production)
sudo journalctl -u nclweb -f
```

### Disk Usage
```bash
# Check PDB file storage
du -sh data/pdb_files/

# Clean old jobs (if needed)
find data/pdb_files/ -type d -mtime +30 -exec rm -rf {} \;
```

## Troubleshooting

### Backend won't start
```bash
# Check Python environment
source venv/bin/activate
python --version

# Check dependencies
pip list | grep -E "(fastapi|uvicorn|gunicorn)"

# Check .env file
cat .env

# Check port availability
lsof -i :8000
```

### Nginx errors
```bash
# Test configuration
sudo nginx -t

# Check error logs
sudo tail -f /var/log/nginx/error.log

# Restart Nginx
sudo service nginx restart
```

### Email notifications not working
```bash
# Check .env variables
grep SMTP .env

# Test email notifier
python3 -c "
from dotenv import load_dotenv
load_dotenv()
from py.email_notifier import EmailNotifier
notifier = EmailNotifier()
print('Enabled:', notifier.enabled)
"
```

### Database issues
```bash
# Check database file
ls -lh data/ncle.db

# Backup database
cp data/ncle.db data/ncle.db.backup_$(date +%Y%m%d_%H%M%S)

# Check tables
sqlite3 data/ncle.db ".tables"
```

## Performance Tuning

### Gunicorn Workers
Default: 4 workers. Adjust based on CPU cores:
```bash
# Formula: (2 * CPU_CORES) + 1
nproc  # Check CPU count
```

Edit in `nclweb.service` or `start_server.sh`:
```bash
-w 8  # For 4-core system
```

### Nginx Caching (optional)
Add to nginx.conf for static files:
```nginx
location ~* \.(jpg|jpeg|png|gif|ico|css|js)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

## Updates

### Deploy New Version
```bash
cd /home/ianms/git_repos/NCLEweb
git pull

# Production (systemd)
sudo systemctl restart nclweb

# WSL (manual)
pkill -f 'gunicorn.*backend:app'
./start_server.sh
```

### Database Migration (if needed)
```bash
# Backup first
cp data/ncle.db data/ncle.db.backup_$(date +%Y%m%d_%H%M%S)

# Run migration script (if you create one)
python py/migrate_db.py
```

## Architecture

```
┌─────────┐         ┌────────────┐         ┌──────────────┐
│  User   │ ──────> │   Nginx    │ ──────> │   Gunicorn   │
│ Browser │  HTTPS  │  (Port 80  │   HTTP  │  (4 workers) │
└─────────┘         │   443)     │         │  Port 8000   │
                    └────────────┘         └──────────────┘
                           │                       │
                           │                       │
                    Static Files            FastAPI Backend
                    (HTML/CSS/JS)           (API Endpoints)
                                                   │
                                                   ├──> SQLite DB
                                                   ├──> EntDetect
                                                   └──> Email SMTP
```

## Support

For issues or questions:
- Check logs first (see Monitoring section)
- Review troubleshooting steps
- Contact: your_email@example.com
