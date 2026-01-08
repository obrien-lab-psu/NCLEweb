# NCLE Web - Gaussian Entanglement Analysis

Web application for calculating Native Gaussian Entanglement (GE) from PDB structures.

## Architecture

**Frontend (static):**
* Single-page app: upload PDB, show NGL viewer, show results table
* Served as static files by Apache

**Backend (Python FastAPI):**
* Accepts PDB uploads via REST API
* Runs Gaussian Entanglement analysis
* Returns raw Native GE results as CSV or JSON
* Runs with uvicorn behind Apache reverse proxy

**Components:**
* `py/api_wrapper.py` - Simplified interface to gaussian_entanglement
* `py/backend.py` - FastAPI server with `/api/analyze` endpoint
* `py/gaussian_entanglement.py` - Core analysis engine (existing)

---

## Quick Start (Local Development)

### Prerequisites
```bash
pip install fastapi uvicorn[standard] pandas numpy scipy biopython MDAnalysis topoly
```

### Run Backend
```bash
cd py
python backend.py
```
API available at `http://localhost:8000`

### Test API
```bash
# Health check
curl http://localhost:8000/

# Analyze PDB
curl -X POST -F "file=@structure.pdb" http://localhost:8000/api/analyze

# Get JSON results
curl -X POST -F "file=@structure.pdb" http://localhost:8000/api/analyze-json
```

---

## API Endpoints

### `GET /`
Health check endpoint

**Response:**
```json
{
  "status": "online",
  "service": "NCLE Gaussian Entanglement API",
  "version": "1.0.0"
}
```

### `POST /api/analyze`
Upload PDB file and get CSV results (pipe-delimited)

**Request:**
- Content-Type: multipart/form-data
- Body: file (PDB file, max 20 MB)

**Response:**
- Content-Type: text/csv
- Columns: ID, i, j, crossingsN, crossingsC, gn, gc, GLNn, GLNc, TLNn, TLNc, CCbond, ENT, absent_crossingsN, absent_crossingsC

### `POST /api/analyze-json`
Upload PDB file and get JSON results

**Response:**
```json
{
  "success": true,
  "pdb_id": "structure_name",
  "num_entanglements": 5,
  "results": [
    {
      "ID": "1ABC",
      "i": 10,
      "j": 50,
      "gn": 0.75,
      "gc": 0.82,
      ...
    }
  ]
}
```

---

## Server Deployment (Apache + Ubuntu)

### Step 1: Server Setup
```bash
# On Ubuntu server
sudo apt update
sudo apt install python3 python3-pip python3-venv apache2

# Create project directory
sudo mkdir -p /var/www/ncleweb
cd /var/www/ncleweb

# Transfer files (use sftp, git clone, or scp)

# Set up Python environment
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn[standard] pandas numpy scipy biopython MDAnalysis topoly

# Test manually
cd py
python backend.py
```

### Step 2: Systemd Service
Create `/etc/systemd/system/ncleweb.service`:
```ini
[Unit]
Description=NCLE Web FastAPI Backend
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/ncleweb/py
Environment="PATH=/var/www/ncleweb/venv/bin"
ExecStart=/var/www/ncleweb/venv/bin/uvicorn backend:app --host 127.0.0.1 --port 8000
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