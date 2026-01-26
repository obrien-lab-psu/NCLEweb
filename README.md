# NCLE Web - Non-covalent Lasso Entanglement Analyzer

Web application for calculating Non-covalent Lasso Entanglement from PDB structures using Gaussian Entanglement analysis.

🌐 **Live Site**: https://ncleweb.org

## Current Status

**Demo Deployment** (Home Server)
- ✅ Live and accessible at https://ncleweb.org
- ✅ Protected by Cloudflare (DDoS protection, SSL, rate limiting)
- ✅ Email notifications enabled
- ✅ Custom organism support with clustering cutoffs
- 📅 Demo period: 1 week
- 🔄 Migration to production server planned after approval

## Architecture

**Frontend (HTML/CSS/JS):**
* Landing page with feature showcase
* Job submission form with organism selection (E. coli, Human, Yeast, Custom)
* Interactive NGL viewer for structure visualization
* Results browser with filtering and sorting
* Served as static files by Nginx

**Backend (Python FastAPI):**
* RESTful API for job submission and management
* Background job processing with status tracking
* Email notifications on job completion
* SQLite database for job persistence
* Clustering with organism-specific or custom cutoffs
* Runs with Gunicorn + Uvicorn workers behind Nginx reverse proxy

**Infrastructure:**
* Nginx reverse proxy on port 80/443
* Cloudflare CDN and DDoS protection
* Rate limiting: 10 API requests/minute per IP
* SSL/TLS encryption (Cloudflare Flexible mode)

**Components:**
* `py/backend.py` - FastAPI server with job management endpoints
* `py/api_wrapper.py` - Interface to EntDetect gaussian_entanglement
* `py/database.py` - SQLite database models and operations
* `py/email_notifier.py` - SMTP email notification system
* `index.html` - Landing page
* `submit.html` - Job submission form
* `browse.html` - Job browser
* `results.html` - Results viewer with NGL integration

---

## Quick Start

### For Demo/Production Server Maintenance

**Check server status:**
```bash
# Backend running?
ps aux | grep gunicorn | grep -v grep

# Nginx running?
sudo service nginx status
```

**View logs:**
```bash
# Backend logs
tail -f ~/git_repos/NCLEweb/logs/access.log
tail -f ~/git_repos/NCLEweb/logs/error.log

# Nginx logs
tail -f ~/git_repos/NCLEweb/logs/nginx_access.log
tail -f ~/git_repos/NCLEweb/logs/nginx_error.log
```

**Restart services if needed:**
```bash
# Restart backend
pkill -f 'gunicorn.*backend:app'
cd ~/git_repos/NCLEweb && nohup ./start_server.sh > /dev/null 2>&1 &

# Restart Nginx
sudo service nginx restart
```

**Update application:**
```bash
cd ~/git_repos/NCLEweb
git pull
pkill -f gunicorn
./start_server.sh
```

### For Local Development

**Prerequisites:**
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install EntDetect (required for gaussian entanglement analysis)
pip install git+https://github.com/obrien-lab-psu/EntDetect.git

# Install additional packages
pip install sqlalchemy python-multipart
```

**Run backend (development mode):**
```bash
cd ~/git_repos/NCLEweb
source venv/bin/activate

# Start backend on port 8000 (or any available port)
uvicorn py.backend:app --reload --host 127.0.0.1 --port 8000
```

**Access locally:**
- Open HTML files directly in browser: `file:///path/to/NCLEweb/index.html`
- Frontend automatically uses localhost:8000 when accessed via file:// protocol
- Backend API: http://127.0.0.1:8000
- API docs: http://127.0.0.1:8000/docs

**Note:** The frontend uses dynamic API URLs:
- When opened locally (file:// protocol): API calls go to http://127.0.0.1:8000
- When served via production domain: API calls go to https://your-domain.com
This allows seamless testing locally and deployment to production without code changes.

---

## Deployment

See detailed deployment guides in the `deploy/` directory:

- **`deploy/HOME_SERVER_SETUP.md`** - Complete guide for WSL/home PC deployment (current setup)
- **`deploy/SERVER_SETUP.md`** - Production server setup (DigitalOcean, Linode, etc.)
- **`deploy/CLOUDFLARE_SETUP.md`** - Cloudflare configuration and security
- **`deploy/README.md`** - Deployment overview and options

**Current deployment configuration:**
- Domain: ncleweb.org
- Server: Home PC (WSL2 on Windows)
- Public IP: 71.58.195.248 (forwarded through router)
- Cloudflare: Proxied (orange cloud ON)
- SSL Mode: Flexible (Cloudflare → User: HTTPS, Cloudflare → Server: HTTP)

**Quick deployment (WSL):**
```bash
./deploy/deploy_wsl.sh
```

---

## API Endpoints

### Job Submission

**`POST /api/submit-job`**

Submit a PDB structure for analysis.

**Request:**
- Content-Type: multipart/form-data
- Parameters:
  - `file`: PDB file (max 50MB)
  - `job_name`: Display name for the job
  - `uniprot_id`: UniProt ID (optional)
  - `email`: Email for notifications
  - `organism`: Ecoli, Human, Yeast, or custom name
  - `cluster_cutoff`: Clustering cutoff (optional, for custom organisms)
  - `ent_detection_method`: Detection method - 1 (GLN-based), 2 (TLN-based), or 3 (Consensus, default)
  - `description`: Job description (optional)

**Response:**
```json
{
  "success": true,
  "job_id": "uuid-string",
  "message": "Job submitted successfully"
}
```

### Job Management

**`GET /api/jobs`**

Get list of all jobs with filtering and pagination.

**Parameters:**
- `status`: Filter by status (pending, processing, completed, failed)
- `offset`: Pagination offset (default: 0)
- `limit`: Results per page (default: 50)

**Response:**
```json
{
  "success": true,
  "total": 100,
  "count": 50,
  "offset": 0,
  "jobs": [
    {
      "job_id": "uuid",
      "job_name": "My Analysis",
      "status": "completed",
      "num_entanglements": 42,
      "upload_timestamp": "2026-01-12T00:00:00",
      ...
    }
  ]
}
```

**`GET /api/job/{job_id}`**

Get detailed information about a specific job including results.

**Response:**
```json
{
  "success": true,
  "job": {
    "job_id": "uuid",
    "job_name": "My Analysis",
    "status": "completed",
    ...
  },
  "results": [...],
  "hq_results": [...],
  "clustered_results": [...]
}
```

**`GET /api/download/{job_id}`**

Download results as CSV file.

---

## Features

### Custom Organism Support
- Pre-configured organisms: E. coli (cutoff: 57), Human (cutoff: 52), Yeast (cutoff: 49)
- Custom organism analysis with user-specified clustering cutoffs
- Dynamic form validation for custom parameters

### Email Notifications
- Automatic email on job completion
- Includes job details and direct link to results
- SMTP configuration via environment variables (.env file)

### Interactive Results Visualization
- NGL Viewer integration for 3D structure display
- Support for both all-atom and coarse-grained structures
- Automatic detection of structure type
- Multi-chain protein support

### Job Management
- Browse all submitted jobs
- Filter by status (pending, processing, completed, failed)
- Search and pagination
- Download results as CSV

### Security & Performance
- Cloudflare DDoS protection and CDN
- Rate limiting: 10 API requests/minute per IP
- File upload validation (50MB max, PDB format)
- Background job processing (non-blocking submissions)
- SQLite database for job persistence

---

## Environment Configuration

Create a `.env` file in the project root:

```bash
# SMTP Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_app_password
FROM_EMAIL=your_email@gmail.com
```

**Note**: For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833), not your regular password.

---

## Project Structure

```
NCLEweb/
├── index.html              # Landing page
├── submit.html             # Job submission form
├── browse.html             # Job browser
├── results.html            # Results viewer with NGL
├── styles.css              # Global styles
├── app.js                  # Frontend JavaScript
├── .env                    # Environment variables (not in git)
├── requirements.txt        # Python dependencies
├── start_server.sh         # Backend startup script
├── py/
│   ├── backend.py          # FastAPI server
│   ├── api_wrapper.py      # EntDetect interface
│   ├── database.py         # SQLite models
│   ├── email_notifier.py   # Email notifications
│   └── run_nativeNCLE.py   # Analysis runner
├── data/
│   ├── ncle.db             # SQLite database
│   └── pdb_files/          # Uploaded PDB files (by job_id)
├── deploy/
│   ├── HOME_SERVER_SETUP.md    # WSL deployment guide
│   ├── SERVER_SETUP.md         # Production server guide
│   ├── CLOUDFLARE_SETUP.md     # Cloudflare configuration
│   ├── nginx.conf              # Nginx production config
│   ├── nclweb.service          # Systemd service file
│   ├── deploy.sh               # Production deployment script
│   └── deploy_wsl.sh           # WSL deployment script
└── structure_files/        # Example PDB files
```

---

## Maintenance

### Monitor Cloudflare Analytics
- Dashboard: https://dash.cloudflare.com
- View traffic, threats blocked, bandwidth usage
- Check Security → Events for blocked attacks

### Database Backups
```bash
# Manual backup
cp data/ncle.db data/ncle.db.backup_$(date +%Y%m%d_%H%M%S)

# Automated backups (add to cron)
crontab -e
# Add: 0 2 * * * cp ~/git_repos/NCLEweb/data/ncle.db ~/backups/ncle.db.backup_$(date +\%Y\%m\%d)
```

### Clean Old Jobs
```bash
# Remove job files older than 30 days
find data/pdb_files/ -type d -mtime +30 -exec rm -rf {} \;
```

### Disk Usage Monitoring
```bash
# Check overall disk space
df -h

# Check PDB files storage
du -sh data/pdb_files/

# Check largest job directories
du -sh data/pdb_files/* | sort -rh | head -10
```

---

## Troubleshooting

### Site Not Loading
```bash
# Check if backend is running
ps aux | grep gunicorn

# Check if Nginx is running
sudo service nginx status

# Check logs for errors
tail -f logs/error.log
tail -f logs/nginx_error.log
```

### Backend Won't Start
```bash
# Check Python environment
source venv/bin/activate
python --version

# Check dependencies
pip list | grep -E "(fastapi|uvicorn|gunicorn)"

# Check .env file exists
cat .env

# Check port availability
lsof -i :8000
```

### Email Notifications Not Working
```bash
# Test email configuration
python3 -c "
from dotenv import load_dotenv
load_dotenv()
from py.email_notifier import EmailNotifier
notifier = EmailNotifier()
print('Enabled:', notifier.enabled)
print('SMTP Host:', notifier.smtp_host)
print('SMTP User:', notifier.smtp_user)
"
```

### Port Forwarding Issues
```bash
# Check Windows port proxy (PowerShell as Admin)
netsh interface portproxy show v4tov4

# Re-add if missing
$WSL_IP = (wsl hostname -I).Trim()
netsh interface portproxy add v4tov4 listenport=80 listenaddress=0.0.0.0 connectport=80 connectaddress=$WSL_IP
netsh interface portproxy add v4tov4 listenport=443 listenaddress=0.0.0.0 connectport=443 connectaddress=$WSL_IP
```

---

## Migration to Production Server

When demo is approved, migrate to dedicated hosting:

1. **Set up new server** (DigitalOcean, Linode, etc.)
2. **Deploy application**: Follow `deploy/SERVER_SETUP.md`
3. **Migrate database**: Copy `data/ncle.db` to new server
4. **Update Cloudflare DNS**: Change A record to new server IP
5. **Test**: Verify site works on new server
6. **Switch**: DNS propagates automatically (5-30 minutes)
7. **Clean up**: Stop home server, remove port forwarding

No downtime needed - Cloudflare enables seamless migration!

---

## Credits

- **Backend**: FastAPI, Uvicorn, Gunicorn
- **Database**: SQLite, SQLAlchemy
- **Frontend**: NGL Viewer for structure visualization
- **Infrastructure**: Nginx, Cloudflare
- **Analysis**: EntDetect Gaussian Entanglement library

---

## License

See LICENSE file for details.

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Start service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable ncleweb
sudo systemctl start ncleweb
sudo systemctl status ncleweb

# View logs
sudo journalctl -u ncleweb -f
```

### Step 3: Apache Configuration
Create `/etc/apache2/sites-available/ncleweb.conf`:
```apache
<VirtualHost *:80>
    ServerName your-domain.com
    DocumentRoot /var/www/ncleweb
    
    # Serve static frontend
    <Directory /var/www/ncleweb>
        Options -Indexes +FollowSymLinks
        AllowOverride None
        Require all granted
    </Directory>
    
    # Proxy API to FastAPI backend
    ProxyPreserveHost On
    ProxyPass /api http://127.0.0.1:8000/api
    ProxyPassReverse /api http://127.0.0.1:8000/api
    
    ErrorLog ${APACHE_LOG_DIR}/ncleweb_error.log
    CustomLog ${APACHE_LOG_DIR}/ncleweb_access.log combined
</VirtualHost>
```

Enable site:
```bash
sudo a2enmod proxy proxy_http
sudo a2ensite ncleweb
sudo apache2ctl configtest
sudo systemctl reload apache2
```

### Step 4: HTTPS (Let's Encrypt)
```bash
sudo apt install certbot python3-certbot-apache
sudo certbot --apache -d your-domain.com
```

---

## Network Access Options

### Option A: Public Internet (Port Forwarding)
- Forward ports 80/443 on your router to the server
- Use a domain with static IP or dynamic DNS (DuckDNS, No-IP)

### Option B: Cloudflare Tunnel (Recommended for Home Hosting)
- No port forwarding needed
- Free HTTPS
- DDoS protection
```bash
# Install cloudflared
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# Set up tunnel
cloudflared tunnel login
cloudflared tunnel create ncleweb
cloudflared tunnel route dns ncleweb your-domain.com
```

### Option C: VPN/Internal Only
- Use Tailscale, Wireguard, or ZeroTier
- Access only from trusted devices

---

## Security Checklist

**Implemented:**
- ✅ File validation (.pdb only)
- ✅ Size limits (20 MB)
- ✅ Non-root execution (www-data user)
- ✅ Temporary file cleanup
- ✅ Input sanitization

**Recommended:**
- ⚠️ Rate limiting (Apache mod_ratelimit or Cloudflare)
- ⚠️ Timeout limits on analysis
- ⚠️ Firewall rules (ufw allow 80,443)
- ⚠️ Regular updates: `sudo apt update && sudo apt upgrade`
- ⚠️ Log monitoring: `sudo journalctl -u ncleweb -f`

---

## Troubleshooting

### Backend won't start
```bash
# Check logs
sudo journalctl -u ncleweb -n 50 --no-pager

# Test manually
cd /var/www/ncleweb
source venv/bin/activate
cd py
python backend.py
```

### Apache proxy errors
```bash
# Verify proxy modules
sudo apache2ctl -M | grep proxy

# Test backend directly
curl http://localhost:8000/

# Check Apache logs
sudo tail -f /var/log/apache2/ncleweb_error.log
```

### Analysis failures
- Verify PDB file format
- Check Python dependencies are installed
- Review structure for missing residues
- Check backend logs for specific errors

---

## File Structure
```
NCLEweb/
├── index.html              # Frontend
├── app.js                  # Frontend logic
├── styles.css              # Styling
├── py/
│   ├── api_wrapper.py          # Simplified GE interface
│   ├── backend.py              # FastAPI server ⭐
│   ├── gaussian_entanglement.py # Core analysis
│   └── run_nativeNCLE.py       # Original example
└── README.md
```

---

## Development Workflow

1. **Local testing:** Run `python py/backend.py`, test with frontend
2. **Transfer to server:** Use `sftp` or `git push/pull`
3. **Restart service:** `sudo systemctl restart ncleweb`
4. **Check logs:** `sudo journalctl -u ncleweb -f`

---

## Future Enhancements

- **Job Queue:** RQ/Celery for long-running analyses with progress tracking
- **Database:** PostgreSQL for storing results
- **Caching:** Redis for repeated structure lookups
- **Batch Processing:** Multiple PDB uploads
- **3D Visualization:** Interactive entanglement display in NGL
- **User Accounts:** Authentication and history

---

## License

See LICENSE file for details.

## Testing on Ian's Mac
1. start backend. 
2. file:///Users/IanSitarik/git_repos/NCLEweb/index.html. 