# Home PC Server Setup for NCLEWEB.ORG (Demo Deployment)

## Overview
This guide sets up your Windows PC (WSL) as a temporary server for demo purposes.

**Duration**: 1 week demo
**Cost**: $0 (using existing PC)

## Important Considerations

### Pros:
✅ No hosting costs
✅ Full control
✅ Easy to troubleshoot (direct access)
✅ Perfect for short demos

### Cons:
⚠️ PC must stay on 24/7 during demo
⚠️ Home IP may change (solved with Cloudflare)
⚠️ Upload speed limits (home internet)
⚠️ Security exposure (mitigated with Cloudflare)
⚠️ Router configuration required

### Security Note:
Using Cloudflare with "Proxied" DNS (orange cloud ON) hides your real home IP from visitors, adding a security layer.

## Step 1: Check Your Network Setup

### Find Your Public IP:

```bash
# Run in WSL
curl ifconfig.me
```

Save this IP - you'll need it for router configuration.

### Check Internet Speed:

Visit: https://www.speedtest.net

**Minimum recommended:**
- Upload: 5+ Mbps (for smooth file uploads)
- Download: 10+ Mbps

### Check Router Access:

You'll need access to your router's admin panel. Common addresses:
- http://192.168.1.1
- http://192.168.0.1
- http://10.0.0.1

Check your router model if these don't work.

## Step 2: Deploy Application Locally

### Install and Configure:

```bash
cd /home/ianms/git_repos/NCLEweb

# Run WSL deployment script
./deploy/deploy_wsl.sh
```

This installs:
- Nginx on port 80
- Backend with Gunicorn

### Configure Backend Base URL:

We need to update the email notification URL to use your domain:

```bash
nano py/backend.py

# Find line around 323:
# results_url = f"{base_url}/results.html?job_id={job_id}"

# Change to:
# results_url = f"https://ncleweb.org/results.html?job_id={job_id}"
```

Or just use this quick fix:

```bash
cd /home/ianms/git_repos/NCLEweb
```

Let me create a patch for this...

### Start the Server:

```bash
# Start backend (in background)
nohup ./start_server.sh > /dev/null 2>&1 &

# Check if Nginx is running
sudo service nginx status

# If not running:
sudo service nginx start
```

### Test Locally:

```bash
# Should return HTML
curl http://localhost

# Should return backend response
curl http://localhost:8000/api/health
```

## Step 3: Configure Router Port Forwarding

### Access Router Admin Panel:

1. Open browser: http://192.168.1.1 (or your router's IP)
2. Login with admin credentials (check router label/manual)

### Add Port Forwarding Rules:

You need to forward these ports from your router to your PC:

**Port 80 (HTTP):**
- External Port: 80
- Internal Port: 80
- Internal IP: Your PC's local IP (find with: `hostname -I` in WSL)
- Protocol: TCP
- Name: ncleweb-http

**Port 443 (HTTPS):**
- External Port: 443
- Internal Port: 443
- Internal IP: Your PC's local IP
- Protocol: TCP
- Name: ncleweb-https

### Find Your PC's Local IP:

```bash
# In WSL, get Windows host IP
cat /etc/resolv.conf | grep nameserver | awk '{print $2}'

# Or from Windows PowerShell:
ipconfig

# Look for "IPv4 Address" under your active network adapter
# Usually starts with 192.168.x.x
```

**Important**: Forward to your **Windows host IP**, not WSL IP!

### Router-Specific Guides:

- **Netgear**: Advanced → Advanced Setup → Port Forwarding
- **TP-Link**: Forwarding → Virtual Servers
- **Linksys**: Security → Apps and Gaming → Port Range Forwarding
- **ASUS**: WAN → Virtual Server/Port Forwarding
- **D-Link**: Advanced → Port Forwarding

Search "port forwarding [your router model]" for specific instructions.

## Step 4: Configure WSL for Port Forwarding

WSL2 requires Windows firewall rules to forward ports:

### Run in Windows PowerShell (as Administrator):

```powershell
# Get WSL IP
wsl hostname -I

# Add firewall rules (replace WSL_IP with the IP from above)
$WSL_IP = "172.x.x.x"  # Replace with your WSL IP

# Allow port 80
netsh interface portproxy add v4tov4 listenport=80 listenaddress=0.0.0.0 connectport=80 connectaddress=$WSL_IP

# Allow port 443
netsh interface portproxy add v4tov4 listenport=443 listenaddress=0.0.0.0 connectport=443 connectaddress=$WSL_IP

# Allow through Windows Firewall
New-NetFirewallRule -DisplayName "WSL Nginx HTTP" -Direction Inbound -LocalPort 80 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "WSL Nginx HTTPS" -Direction Inbound -LocalPort 443 -Protocol TCP -Action Allow

# Verify port proxy rules
netsh interface portproxy show v4tov4
```

### Persist Port Forwarding on WSL Restart:

Create a script that runs on Windows startup:

```powershell
# Save this as: C:\Users\YourName\wsl-port-forward.ps1

$WSL_IP = (wsl hostname -I).Trim()

# Remove old rules
netsh interface portproxy delete v4tov4 listenport=80 listenaddress=0.0.0.0
netsh interface portproxy delete v4tov4 listenport=443 listenaddress=0.0.0.0

# Add new rules with current WSL IP
netsh interface portproxy add v4tov4 listenport=80 listenaddress=0.0.0.0 connectport=80 connectaddress=$WSL_IP
netsh interface portproxy add v4tov4 listenport=443 listenaddress=0.0.0.0 connectport=443 connectaddress=$WSL_IP

Write-Host "WSL Port forwarding configured for IP: $WSL_IP"
```

Then add to Task Scheduler to run on startup:
1. Open Task Scheduler
2. Create Task → Name: "WSL Port Forward"
3. Triggers → New → At startup
4. Actions → New → Program: `powershell.exe`
5. Arguments: `-ExecutionPolicy Bypass -File "C:\Users\YourName\wsl-port-forward.ps1"`
6. Run with highest privileges: ✓

## Step 5: Configure Cloudflare DNS

### Add DNS Records:

1. Go to: https://dash.cloudflare.com
2. Select **ncleweb.org**
3. Go to **DNS** → **Records**

**A Record:**
```
Type: A
Name: @
IPv4: YOUR_PUBLIC_IP (from curl ifconfig.me)
Proxy: ON (orange cloud) ← CRITICAL for security
TTL: Auto
```

**CNAME Record:**
```
Type: CNAME
Name: www
Target: ncleweb.org
Proxy: ON (orange cloud) ← CRITICAL
TTL: Auto
```

### Configure SSL/TLS:

**Important for home server:**

1. **SSL/TLS** → **Overview** → Set to **"Flexible"**
   - (Not "Full" because you don't have a valid SSL cert on your home server)

2. **Edge Certificates**:
   - Enable **Always Use HTTPS**
   - Enable **Automatic HTTPS Rewrites**

### Why "Flexible" Mode:
- Cloudflare → User: HTTPS (encrypted)
- Cloudflare → Your Home: HTTP (unencrypted, but over Cloudflare's network)
- This is fine for demos since Cloudflare handles public SSL

### Security Settings:

1. **Security** → **Settings**:
   - Security Level: **High** (extra protection for home IP)
   - Challenge Passage: 30 minutes

2. **Security** → **WAF** → **Create rule**:
   ```
   Rule name: Rate limit API
   Field: URI Path | contains | /api/submit-job
   Then: Challenge if rate > 5 per minute
   ```

## Step 6: Handle Dynamic IP (Optional but Recommended)

Home IPs can change. Set up auto-update:

### Install Cloudflare DDNS Updater:

```bash
# In WSL
cd ~
git clone https://github.com/timothymiller/cloudflare-ddns-updater.git
cd cloudflare-ddns-updater
```

### Configure:

```bash
nano config.json
```

Add:
```json
{
  "cloudflare": [
    {
      "authentication": {
        "api_token": "YOUR_CLOUDFLARE_API_TOKEN"
      },
      "zone_id": "YOUR_ZONE_ID",
      "subdomains": [
        {
          "name": "@",
          "proxied": true
        },
        {
          "name": "www",
          "proxied": true
        }
      ]
    }
  ]
}
```

### Get Cloudflare API Token:

1. Cloudflare Dashboard → My Profile → API Tokens
2. Create Token → Edit zone DNS template
3. Zone Resources → Include → Specific zone → ncleweb.org
4. Copy the token

### Get Zone ID:

1. Cloudflare Dashboard → Select ncleweb.org
2. Right sidebar → API section → Zone ID
3. Copy the Zone ID

### Run DDNS Updater:

```bash
# Test it
python3 cloudflare-ddns.py

# Run in background
nohup python3 cloudflare-ddns.py > /dev/null 2>&1 &

# Or add to cron (every 5 minutes)
crontab -e
# Add:
*/5 * * * * cd ~/cloudflare-ddns-updater && python3 cloudflare-ddns.py
```

Alternatively, use a simpler tool:

```bash
# Install cloudflare-ddns
pip3 install cloudflare-ddns

# Configure (interactive)
cloudflare-ddns --configure

# Run as service
cloudflare-ddns --daemon
```

## Step 7: Test Your Deployment

### DNS Propagation:

```bash
# Check DNS
nslookup ncleweb.org

# Should show Cloudflare IPs, not your home IP
# This confirms proxy is working
```

### Test from External Network:

Use your phone (disable WiFi, use cellular):
- Visit: https://ncleweb.org
- Should load your site

Or use online test:
- https://www.whatsmydns.net/#A/ncleweb.org

### Test API:

```bash
curl -I https://ncleweb.org/api/health
```

### Submit Test Job:

1. Go to https://ncleweb.org
2. Click "Submit Analysis"
3. Upload test PDB
4. Check email for notification

## Step 8: Monitoring During Demo

### Keep PC Running:

**Windows Settings:**
1. Settings → System → Power & sleep
2. Set "When plugged in, PC goes to sleep after": **Never**
3. Set "When plugged in, turn off screen after": Your preference

**Prevent WSL Shutdown:**
Keep a terminal open or:
```bash
# In WSL, run a keep-alive process
while true; do sleep 3600; done &
```

### Monitor Backend:

```bash
# Check backend status
ps aux | grep gunicorn

# View logs
tail -f ~/git_repos/NCLEweb/logs/access.log
tail -f ~/git_repos/NCLEweb/logs/error.log
```

### Monitor Traffic in Cloudflare:

Dashboard → Analytics → Traffic

You can see:
- Number of requests
- Bandwidth usage
- Threats blocked
- Geographic distribution

### Restart if Needed:

```bash
# Restart backend
pkill -f 'gunicorn.*backend:app'
./start_server.sh

# Restart Nginx
sudo service nginx restart
```

## Step 9: Demo Week Checklist

### Before Demo:
- ✅ PC stays on and connected to internet
- ✅ Router port forwarding configured
- ✅ Windows firewall rules set
- ✅ Cloudflare DNS configured (orange cloud ON)
- ✅ Backend running (`ps aux | grep gunicorn`)
- ✅ Nginx running (`sudo service nginx status`)
- ✅ Test submission works end-to-end
- ✅ Email notifications working

### During Demo:
- ✅ Monitor Cloudflare Analytics
- ✅ Check backend logs periodically
- ✅ Have phone ready to restart if needed (via SSH)
- ✅ Test site every morning

### After Demo:
- ✅ Stop backend: `pkill -f 'gunicorn.*backend:app'`
- ✅ Stop Nginx: `sudo service nginx stop`
- ✅ Remove port forwarding rules from router (security)
- ✅ Decide on permanent hosting solution

## Troubleshooting

### Can't Access from Outside:

1. **Check port forwarding**:
   ```bash
   # From external network
   curl http://YOUR_PUBLIC_IP
   ```

2. **Check Windows firewall**:
   ```powershell
   # In PowerShell (Admin)
   netsh interface portproxy show v4tov4
   ```

3. **Check WSL is running**:
   ```bash
   # In WSL
   curl http://localhost
   ```

4. **Verify Cloudflare proxying**:
   ```bash
   dig ncleweb.org
   # Should show Cloudflare IPs (104.x.x.x)
   ```

### Site Loads but API Doesn't Work:

```bash
# Check backend is running
ps aux | grep gunicorn

# Check backend logs
tail -f logs/error.log

# Restart backend
pkill -f gunicorn
./start_server.sh
```

### IP Changed:

If you didn't set up DDNS:

1. Get new public IP: `curl ifconfig.me`
2. Update Cloudflare DNS A record with new IP
3. Wait 5 minutes for propagation

### SSL Errors:

Verify Cloudflare SSL mode is "Flexible":
- Dashboard → SSL/TLS → Overview → Flexible

### Performance Issues:

- Check upload speed: https://www.speedtest.net
- Limit concurrent jobs in backend if needed
- Monitor CPU/RAM usage: `htop`

## Security Notes

### What Cloudflare Protects:

✅ Hides your real home IP address
✅ Blocks DDoS attacks
✅ Rate limiting
✅ Bot protection
✅ SSL/HTTPS for visitors

### What You Should Do:

✅ Keep Windows updated
✅ Don't open other ports unnecessarily
✅ Use strong router admin password
✅ Monitor Cloudflare security events
✅ Remove port forwarding after demo

### What's Still Exposed:

⚠️ If Cloudflare proxy is disabled (gray cloud), your home IP is public
⚠️ Anyone with your IP could try other ports (keep them closed)
⚠️ Always keep orange cloud ON in Cloudflare DNS

## Cost Summary

- **Domain**: Already paid ($9/year)
- **Server**: $0 (using your PC)
- **Cloudflare**: $0 (Free tier)
- **SSL**: $0 (Cloudflare)
- **Electricity**: ~$0.50-2/week (PC running 24/7)

**Total Demo Cost: ~$0.50-2 for electricity**

## Migration to Permanent Hosting

When demo is approved, migrate to production:

1. **Sign up for DigitalOcean** ($6-12/month)
2. **Deploy using deploy.sh**
3. **Update Cloudflare DNS** to new server IP
4. **Test migration** before shutting down home server
5. **Switch DNS** (instant with Cloudflare)
6. **Remove home port forwarding**

No downtime needed - Cloudflare lets you switch seamlessly!

## Quick Reference

```bash
# Start backend
cd ~/git_repos/NCLEweb
./start_server.sh

# Stop backend
pkill -f 'gunicorn.*backend:app'

# Restart Nginx
sudo service nginx restart

# Check if running
ps aux | grep gunicorn
sudo service nginx status

# View logs
tail -f logs/access.log
tail -f logs/error.log

# Get public IP
curl ifconfig.me

# Test locally
curl http://localhost
curl http://localhost:8000/api/health

# Update code
cd ~/git_repos/NCLEweb
git pull
pkill -f gunicorn
./start_server.sh
```
