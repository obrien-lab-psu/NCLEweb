# Cloudflare Setup Guide for NCLE Web

## Overview
Cloudflare will sit between your users and your server, providing DDoS protection, CDN, SSL, and security features.

## Step 1: Choose Your Domain Name

You need to decide on a domain name for your site. Options:

### Option A: Buy a New Domain
- **Recommended registrars**: Namecheap, Google Domains, Cloudflare Registrar
- **Suggested names**: 
  - `ncle-web.com`
  - `ncleanalyzer.com`
  - `lasso-entanglement.org`
  - `nclweb.org`
- **Cost**: $10-15/year typically

### Option B: Use an Existing Domain
If you already own a domain (e.g., `yourdomain.com`), you can use:
- Main domain: `yourdomain.com`
- Subdomain: `ncle.yourdomain.com` or `analyzer.yourdomain.com`

### Option C: Free Options (for testing)
- **No-IP** or **DuckDNS** - Free dynamic DNS
- Good for development/testing, not recommended for production

## Step 2: Add Site to Cloudflare

1. **Log in to Cloudflare**: https://dash.cloudflare.com
2. **Click "Add a Site"**
3. **Enter your domain name** (e.g., `ncle-web.com`)
4. **Select Free Plan** (more than enough for your needs)
5. **Click "Continue"**

Cloudflare will scan your existing DNS records (if any).

## Step 3: Configure DNS Records

After Cloudflare scans your domain, add these DNS records:

### Record 1: Root Domain (A Record)
```
Type: A
Name: @
IPv4 address: YOUR_SERVER_IP
Proxy status: Proxied (orange cloud icon)
TTL: Auto
```

### Record 2: WWW Subdomain (CNAME Record)
```
Type: CNAME
Name: www
Target: your_domain.com
Proxy status: Proxied (orange cloud icon)
TTL: Auto
```

**Finding your server IP:**
```bash
# On your WSL/Linux server, run:
curl ifconfig.me

# Or check with:
hostname -I
```

**Important**: Make sure the orange cloud icon is ON (proxied) - this routes traffic through Cloudflare.

## Step 4: Update Nameservers

Cloudflare will provide you with **two nameservers** like:
```
mia.ns.cloudflare.com
tim.ns.cloudflare.com
```

### Where to Update Nameservers (depends on where you bought domain):

#### Namecheap:
1. Log in to Namecheap
2. Domain List → Manage
3. Find "Nameservers" section
4. Select "Custom DNS"
5. Enter both Cloudflare nameservers
6. Save changes

#### Google Domains:
1. Log in to Google Domains
2. Select your domain
3. Click "DNS" in left menu
4. Click "Use custom name servers"
5. Enter both Cloudflare nameservers
6. Save

#### GoDaddy:
1. Log in to GoDaddy
2. My Products → Domains
3. Click domain name
4. Scroll to "Nameservers"
5. Click "Change"
6. Select "Custom"
7. Enter both Cloudflare nameservers
8. Save

#### Cloudflare Registrar (if you bought through Cloudflare):
Automatically configured - skip this step!

### Propagation Time
- Changes take **15 minutes to 48 hours** to propagate globally
- Usually happens within 1-2 hours
- Check status in Cloudflare dashboard

## Step 5: Configure Cloudflare Settings

Once nameservers are updated (status shows "Active"):

### SSL/TLS Settings:
1. Go to **SSL/TLS** → **Overview**
2. Select **"Full (strict)"** encryption mode
3. Go to **Edge Certificates**
4. Enable **Always Use HTTPS**
5. Enable **Automatic HTTPS Rewrites**
6. Set **Minimum TLS Version** to 1.2

### Security Settings:
1. Go to **Security** → **Settings**
2. **Security Level**: Medium (adjust if getting false positives)
3. **Challenge Passage**: 30 minutes
4. **Browser Integrity Check**: ON

### Firewall Rules (Free tier allows 5):

#### Rule 1: Rate Limit API
```
Field: URI Path
Operator: contains
Value: /api/submit-job

Then: Challenge (CAPTCHA) if more than 5 requests in 1 minute
```

#### Rule 2: Block Common Bots
```
Field: User Agent
Operator: contains
Value: scanner

Then: Block
```

### Page Rules (Optional - Free tier allows 3):

#### Cache Static Files:
```
URL: your_domain.com/*.css
OR
URL: your_domain.com/*.js

Settings:
- Cache Level: Standard
- Browser Cache TTL: 1 year
```

### Performance Settings:
1. Go to **Speed** → **Optimization**
2. Enable **Auto Minify**: Check HTML, CSS, JS
3. Enable **Brotli** compression
4. Enable **Rocket Loader** (test this - may break some JS)

## Step 6: Update Server Configuration

Once Cloudflare is active, update your Nginx config to trust Cloudflare IPs:

```nginx
# Add this inside server block in /etc/nginx/sites-available/nclweb

# Restore real visitor IP from Cloudflare
set_real_ip_from 173.245.48.0/20;
set_real_ip_from 103.21.244.0/22;
set_real_ip_from 103.22.200.0/22;
set_real_ip_from 103.31.4.0/22;
set_real_ip_from 141.101.64.0/18;
set_real_ip_from 108.162.192.0/18;
set_real_ip_from 190.93.240.0/20;
set_real_ip_from 188.114.96.0/20;
set_real_ip_from 197.234.240.0/22;
set_real_ip_from 198.41.128.0/17;
set_real_ip_from 162.158.0.0/15;
set_real_ip_from 104.16.0.0/13;
set_real_ip_from 104.24.0.0/14;
set_real_ip_from 172.64.0.0/13;
set_real_ip_from 131.0.72.0/22;
set_real_ip_from 2400:cb00::/32;
set_real_ip_from 2606:4700::/32;
set_real_ip_from 2803:f800::/32;
set_real_ip_from 2405:b500::/32;
set_real_ip_from 2405:8100::/32;
set_real_ip_from 2a06:98c0::/29;
set_real_ip_from 2c0f:f248::/32;
real_ip_header CF-Connecting-IP;
```

Then restart Nginx:
```bash
sudo nginx -t
sudo service nginx restart
```

## Step 7: SSL Certificate

### Option 1: Cloudflare Origin Certificate (Recommended)
1. In Cloudflare: **SSL/TLS** → **Origin Server**
2. Click **Create Certificate**
3. Use default settings (15 year validity)
4. Copy the certificate and private key
5. Save on your server:
   ```bash
   sudo nano /etc/ssl/cloudflare-cert.pem
   # Paste certificate
   
   sudo nano /etc/ssl/cloudflare-key.pem
   # Paste private key
   
   sudo chmod 600 /etc/ssl/cloudflare-key.pem
   ```
6. Update Nginx config:
   ```nginx
   ssl_certificate /etc/ssl/cloudflare-cert.pem;
   ssl_certificate_key /etc/ssl/cloudflare-key.pem;
   ```

### Option 2: Let's Encrypt (Also works)
Keep using Let's Encrypt as configured in deploy.sh - Cloudflare works with it fine.

## Step 8: Test Your Setup

1. **DNS Propagation**:
   ```bash
   nslookup your_domain.com
   # Should show Cloudflare IPs (104.x.x.x range)
   ```

2. **SSL Test**:
   - Visit https://your_domain.com
   - Check for green padlock
   - View certificate - should show Cloudflare

3. **Cloudflare Check**:
   ```bash
   curl -I https://your_domain.com
   # Look for: "cf-ray" and "cf-cache-status" headers
   ```

4. **Rate Limiting**:
   - Try submitting multiple jobs quickly
   - Should see CAPTCHA challenge after 5 requests

5. **DDoS Protection**:
   - Check **Security** → **Events** in Cloudflare dashboard
   - Should see "Challenge" events for suspicious traffic

## Monitoring

### Cloudflare Dashboard:
- **Analytics**: Traffic, bandwidth, threats blocked
- **Security Events**: Challenges, blocks, bypasses
- **Traffic**: Requests, bandwidth, cache ratio

### Check Protection Status:
```bash
# See if traffic is proxied through Cloudflare
curl -I https://your_domain.com | grep -i cloudflare
```

## Troubleshooting

### Site Not Loading:
1. Check DNS propagation: https://dnschecker.org
2. Verify nameservers updated at registrar
3. Check Cloudflare DNS records are "Proxied" (orange cloud)
4. Ensure server is running and accessible

### SSL Errors:
1. Change Cloudflare SSL mode to "Flexible" temporarily
2. Verify origin certificate installed correctly
3. Check Nginx SSL configuration
4. Review error logs: `sudo tail -f /var/log/nginx/error.log`

### Too Many CAPTCHAs:
1. Lower Security Level: **Security** → **Settings** → Low/Medium
2. Add firewall rule to allow trusted IPs
3. Adjust Challenge Passage time

### Rate Limiting Too Strict:
1. Increase limit in firewall rules
2. Whitelist your own IP for testing
3. Add cookie/token bypass for authenticated users

## Cost

**Cloudflare Free Tier** includes:
- Unlimited DDoS protection
- Global CDN
- Free SSL certificate
- 5 firewall rules
- 3 page rules
- Basic analytics
- 100% uptime guarantee

This is more than sufficient for NCLE Web.

**Pro tier ($20/month)** adds:
- WAF (Web Application Firewall)
- 20 firewall rules
- Image optimization
- Mobile optimization

Only upgrade if you need WAF or more rules.

## Domain Naming Recommendations

For your NCLE (Non-covalent Lasso Entanglement) analyzer:

**Good options:**
- `ncle-web.com` / `ncle-web.org`
- `nclweb.org`
- `ncle-analyzer.com`
- `lasso-entanglement.org`
- `entanglement-analyzer.org`

**Avoid:**
- Very long names
- Hard to spell names
- Names with hyphens if possible (but okay if needed)
- Trademarked terms

Check availability:
- Namecheap: https://www.namecheap.com
- Google Domains: https://domains.google
- Cloudflare Registrar: https://www.cloudflare.com/products/registrar/

## Next Steps After Setup

1. Update `deploy/nginx.conf` with your actual domain name
2. Update `py/backend.py` if you have hardcoded URLs for email links
3. Test full workflow: submit job → receive email → view results
4. Monitor Cloudflare analytics for first week
5. Adjust security settings based on traffic patterns

## Support

- Cloudflare Docs: https://developers.cloudflare.com
- Community Forum: https://community.cloudflare.com
- Status Page: https://www.cloudflarestatus.com
