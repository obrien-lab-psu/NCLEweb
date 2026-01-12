# Production Server Setup Guide for NCLEWEB.ORG

## Step 1: Choose a Hosting Provider

### Recommended Options:

#### DigitalOcean (Easiest for beginners)
- **Price**: $6/month (1GB RAM, 1 CPU, 25GB SSD)
- **Pros**: Simple interface, excellent docs, $200 free credit for 60 days
- **Best for**: Beginners, quick setup
- **Sign up**: https://www.digitalocean.com

#### Linode (by Akamai)
- **Price**: $5/month (1GB RAM, 1 CPU, 25GB SSD)
- **Pros**: Reliable, good performance, $100 free credit
- **Best for**: Good balance of features and price
- **Sign up**: https://www.linode.com

#### Vultr
- **Price**: $6/month (1GB RAM, 1 CPU, 25GB SSD)
- **Pros**: Multiple locations, good speeds
- **Best for**: International users
- **Sign up**: https://www.vultr.com

#### AWS Lightsail
- **Price**: $5/month (1GB RAM, 1 CPU, 40GB SSD)
- **Pros**: Part of AWS ecosystem, 3 months free
- **Best for**: If you plan to use other AWS services
- **Sign up**: https://aws.amazon.com/lightsail

**Recommendation**: Start with **DigitalOcean** - it's the most beginner-friendly.

### Server Requirements:
- **Minimum**: 1GB RAM, 1 CPU, 25GB SSD
- **Recommended**: 2GB RAM, 2 CPU, 50GB SSD ($12-15/month)
- **OS**: Ubuntu 22.04 LTS (or 24.04 LTS)
- **Location**: Choose closest to your users

## Step 2: Create Your Server

### DigitalOcean Instructions:

1. **Sign up and verify email**
2. **Create a Droplet**:
   - Click "Create" → "Droplets"
   - Choose an image: **Ubuntu 22.04 LTS**
   - Choose size: **Basic $6/month** (or $12 for 2GB)
   - Choose datacenter: **New York, San Francisco, or closest to you**
   - Authentication: **SSH keys** (recommended) or **Password**
   - Hostname: `ncleweb-prod`
   - Click "Create Droplet"

3. **Get your IP address**: 
   - Appears on the droplets page
   - Example: `164.92.123.45`
   - Save this - you'll need it!

### Setting Up SSH Key (Recommended for security):

If you chose SSH key authentication:

```bash
# On your local machine (WSL), generate SSH key if you don't have one:
ssh-keygen -t ed25519 -C "your_email@example.com"

# Display your public key:
cat ~/.ssh/id_ed25519.pub

# Copy the output and paste it into DigitalOcean when creating droplet
```

## Step 3: Initial Server Setup

### Connect to Your Server:

```bash
# Replace YOUR_SERVER_IP with actual IP
ssh root@YOUR_SERVER_IP

# First time connecting, type 'yes' to confirm fingerprint
```

### Update System:

```bash
apt update && apt upgrade -y
```

### Create Non-Root User:

```bash
# Create user
adduser ianms
# Set password when prompted

# Add to sudo group
usermod -aG sudo ianms

# Copy SSH keys to new user (if using SSH keys)
rsync --archive --chown=ianms:ianms ~/.ssh /home/ianms
```

### Configure Firewall:

```bash
# Allow SSH
ufw allow OpenSSH

# Allow HTTP and HTTPS
ufw allow 'Nginx Full'

# Enable firewall
ufw enable

# Check status
ufw status
```

### Logout and reconnect as new user:

```bash
exit

# Connect as ianms
ssh ianms@YOUR_SERVER_IP
```

## Step 4: Install Required Software

### Install Git:

```bash
sudo apt install -y git
```

### Install Python and Dependencies:

```bash
# Install Python 3.10+ and pip
sudo apt install -y python3 python3-pip python3-venv

# Check version
python3 --version
# Should be 3.10 or higher
```

### Clone Your Repository:

```bash
# Create directory
mkdir -p ~/git_repos
cd ~/git_repos

# Clone repository
git clone https://github.com/obrien-lab-psu/NCLEweb.git
cd NCLEweb
```

### Set Up Python Virtual Environment:

```bash
# Create venv
python3 -m venv venv

# Activate
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Verify installation
pip list | grep -E "(fastapi|uvicorn|sqlalchemy)"
```

### Install EntDetect:

```bash
# Follow EntDetect installation instructions
# This will depend on your EntDetect package
# If it's a separate package, install it:

# Example (adjust based on your setup):
pip install EntDetect
# Or if it's in a separate repo:
# cd ~/git_repos
# git clone https://github.com/your-org/EntDetect.git
# cd EntDetect
# pip install -e .
```

### Create .env File:

```bash
cd ~/git_repos/NCLEweb

# Create .env with your credentials
cat > .env << 'EOF'
# SMTP Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=nclewebnotifications@gmail.com
SMTP_PASS=aeeokyxynrhloihh
FROM_EMAIL=nclewebnotifications@gmail.com
EOF

# Secure the file
chmod 600 .env
```

### Initialize Database:

```bash
# Create data directory if it doesn't exist
mkdir -p ~/git_repos/NCLEweb/data
mkdir -p ~/git_repos/NCLEweb/data/pdb_files

# The database will be created automatically on first run
```

## Step 5: Deploy the Application

### Run Deployment Script:

```bash
cd ~/git_repos/NCLEweb
sudo ./deploy/deploy.sh
```

This script will:
- Install Nginx
- Configure Nginx for ncleweb.org
- Set up SSL with Let's Encrypt
- Create systemd service
- Start the backend

### Manual Steps (if script fails or you want to do it step by step):

#### Install Nginx:
```bash
sudo apt install -y nginx
```

#### Install Certbot:
```bash
sudo apt install -y certbot python3-certbot-nginx
```

#### Copy Nginx Config:
```bash
sudo cp ~/git_repos/NCLEweb/deploy/nginx.conf /etc/nginx/sites-available/nclweb
sudo ln -s /etc/nginx/sites-available/nclweb /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test config
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

#### Set Up SSL Certificate:
```bash
# This will automatically configure SSL
sudo certbot --nginx -d ncleweb.org -d www.ncleweb.org --non-interactive --agree-tos -m nclewebnotifications@gmail.com
```

#### Install Gunicorn:
```bash
source ~/git_repos/NCLEweb/venv/bin/activate
pip install gunicorn
deactivate
```

#### Create Systemd Service:
```bash
sudo cp ~/git_repos/NCLEweb/deploy/nclweb.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable nclweb
sudo systemctl start nclweb
```

#### Check Service Status:
```bash
sudo systemctl status nclweb
```

## Step 6: Configure Cloudflare

### Add DNS Records:

1. Go to **Cloudflare Dashboard**: https://dash.cloudflare.com
2. Select **ncleweb.org**
3. Go to **DNS** → **Records**
4. Add records:

**A Record:**
```
Type: A
Name: @
IPv4: YOUR_SERVER_IP (from Step 2)
Proxy: ON (orange cloud)
TTL: Auto
```

**CNAME Record:**
```
Type: CNAME
Name: www
Target: ncleweb.org
Proxy: ON (orange cloud)
TTL: Auto
```

### Configure SSL/TLS:

1. **SSL/TLS** → **Overview** → Set to **"Full (strict)"**
2. **Edge Certificates**:
   - Enable **Always Use HTTPS**
   - Enable **Automatic HTTPS Rewrites**
   - Minimum TLS Version: **1.2**

### Configure Security:

1. **Security** → **Settings**:
   - Security Level: **Medium**
   - Challenge Passage: **30 minutes**
   - Browser Integrity Check: **ON**

2. **Security** → **WAF** → **Create rule**:
   ```
   Rule Name: Rate limit submissions
   Field: URI Path | contains | /api/submit-job
   Then: Challenge if rate exceeds 5 requests per minute
   ```

## Step 7: Test Your Deployment

### Check DNS Propagation:

```bash
# From your local machine
nslookup ncleweb.org
# Should show Cloudflare IPs (104.x.x.x)
```

### Test Website:

```bash
# Check if site loads
curl -I https://ncleweb.org

# Should see:
# - HTTP/2 200
# - cf-ray: (Cloudflare header)
# - Strict-Transport-Security header
```

### Test Backend API:

```bash
curl https://ncleweb.org/api/health
# Should return health status
```

### Test in Browser:

1. Visit: **https://ncleweb.org**
2. Click **"Get Started"** or **"Submit Analysis"**
3. Fill out the form with a test PDB file
4. Submit and check email for notification

### Monitor Logs:

```bash
# Backend logs
sudo journalctl -u nclweb -f

# Nginx logs
sudo tail -f /var/log/nginx/nclweb_access.log
sudo tail -f /var/log/nginx/nclweb_error.log
```

## Step 8: Ongoing Maintenance

### Update Application:

```bash
cd ~/git_repos/NCLEweb
git pull
sudo systemctl restart nclweb
```

### Monitor Disk Usage:

```bash
# Check overall disk space
df -h

# Check PDB files directory
du -sh ~/git_repos/NCLEweb/data/pdb_files/

# Clean old jobs (older than 30 days)
find ~/git_repos/NCLEweb/data/pdb_files/ -type d -mtime +30 -exec rm -rf {} \;
```

### Monitor Service:

```bash
# Check if service is running
sudo systemctl status nclweb

# View recent logs
sudo journalctl -u nclweb --since "1 hour ago"

# Check for errors
sudo journalctl -u nclweb -p err
```

### Database Backup:

```bash
# Manual backup
cp ~/git_repos/NCLEweb/data/ncle.db ~/backups/ncle.db.backup_$(date +%Y%m%d_%H%M%S)

# Set up automated daily backups (cron)
crontab -e

# Add this line (runs daily at 2 AM):
0 2 * * * cp ~/git_repos/NCLEweb/data/ncle.db ~/backups/ncle.db.backup_$(date +\%Y\%m\%d) && find ~/backups -name "ncle.db.backup_*" -mtime +7 -delete
```

### SSL Certificate Renewal:

```bash
# Test renewal (dry run)
sudo certbot renew --dry-run

# Certbot auto-renews via systemd timer
sudo systemctl status certbot.timer
```

## Troubleshooting

### Service Won't Start:

```bash
# Check logs for errors
sudo journalctl -u nclweb -n 50

# Common issues:
# 1. Port 8000 already in use
sudo lsof -i :8000
sudo pkill -f gunicorn

# 2. Python module not found
source ~/git_repos/NCLEweb/venv/bin/activate
pip install -r requirements.txt

# 3. Permission issues
sudo chown -R ianms:ianms ~/git_repos/NCLEweb
```

### Nginx Errors:

```bash
# Test configuration
sudo nginx -t

# Check error logs
sudo tail -f /var/log/nginx/error.log

# Restart Nginx
sudo systemctl restart nginx
```

### Can't Connect to Site:

```bash
# Check firewall
sudo ufw status

# Check if Nginx is running
sudo systemctl status nginx

# Check if backend is running
sudo systemctl status nclweb

# Check DNS
nslookup ncleweb.org
```

### SSL Issues:

```bash
# Check certificate
sudo certbot certificates

# Force renewal
sudo certbot renew --force-renewal

# Check Cloudflare SSL mode
# Should be "Full (strict)" in Cloudflare dashboard
```

## Security Checklist

- ✅ Firewall enabled (ufw)
- ✅ Non-root user created
- ✅ SSH key authentication (if using)
- ✅ Nginx reverse proxy configured
- ✅ SSL/TLS enabled (via Let's Encrypt + Cloudflare)
- ✅ Rate limiting configured (Cloudflare + Nginx)
- ✅ Security headers enabled (in Nginx config)
- ✅ .env file secured (chmod 600)
- ✅ Automatic updates enabled
- ✅ Cloudflare DDoS protection active

### Enable Automatic Security Updates:

```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
# Select "Yes"
```

### Disable Root Login (Optional, recommended):

```bash
sudo nano /etc/ssh/sshd_config

# Change this line:
PermitRootLogin no

# Restart SSH
sudo systemctl restart sshd
```

## Cost Estimate

**Monthly Costs:**
- Server (DigitalOcean): $6-12/month
- Domain (ncleweb.org): $9/year = $0.75/month
- Cloudflare: $0 (Free tier)
- SSL Certificate: $0 (Let's Encrypt)

**Total: ~$7-13/month**

## Support Resources

- DigitalOcean Docs: https://docs.digitalocean.com
- Nginx Docs: https://nginx.org/en/docs/
- Certbot: https://certbot.eff.org
- Cloudflare Docs: https://developers.cloudflare.com
- Ubuntu Docs: https://help.ubuntu.com

## Quick Reference Commands

```bash
# Service management
sudo systemctl start nclweb      # Start backend
sudo systemctl stop nclweb       # Stop backend
sudo systemctl restart nclweb    # Restart backend
sudo systemctl status nclweb     # Check status

# Nginx
sudo systemctl restart nginx     # Restart Nginx
sudo nginx -t                    # Test config

# Logs
sudo journalctl -u nclweb -f     # Follow backend logs
sudo tail -f /var/log/nginx/nclweb_access.log  # Nginx access
sudo tail -f /var/log/nginx/nclweb_error.log   # Nginx errors

# Updates
cd ~/git_repos/NCLEweb
git pull
sudo systemctl restart nclweb

# Disk space
df -h
du -sh ~/git_repos/NCLEweb/data/

# Database backup
cp ~/git_repos/NCLEweb/data/ncle.db ~/backups/ncle.db.$(date +%Y%m%d)
```
