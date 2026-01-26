# HAMSVIC Complete Deployment Guide

## Overview
This guide covers setting up your Django application on AWS with all required services.

---

## STEP 1: Domain Purchase (GoDaddy/Namecheap)

### Option A: GoDaddy
1. Go to https://www.godaddy.com
2. Search for your domain (e.g., `hamsvic.com` or `hamsvic.in`)
3. `.com` costs ~₹800-1,200/year, `.in` costs ~₹500-700/year
4. Complete purchase with your details

### Option B: Namecheap (Recommended - cheaper)
1. Go to https://www.namecheap.com
2. Search and purchase domain
3. Usually 10-20% cheaper than GoDaddy

**Save your domain credentials - you'll need them later!**

---

## STEP 2: AWS Account Setup

### 2.1 Create AWS Account
1. Go to https://aws.amazon.com
2. Click "Create an AWS Account"
3. Enter email, password, and account name
4. Choose "Personal" or "Business" account
5. Enter payment details (credit/debit card required)
6. Verify phone number
7. Choose "Basic Support - Free"

### 2.2 Enable MFA (Important for Security)
1. Go to IAM → Your Security Credentials
2. Enable MFA (use Google Authenticator app)

### 2.3 Create IAM User (Best Practice)
```
1. Go to IAM → Users → Create User
2. Username: hamsvic-admin
3. Enable "Console access"
4. Attach policies: AdministratorAccess (or specific policies)
5. Save the Access Key ID and Secret Access Key
```

---

## STEP 3: Launch EC2 Instance

### 3.1 Launch Instance
1. Go to EC2 → Instances → Launch Instance
2. **Name:** hamsvic-production
3. **AMI:** Ubuntu Server 24.04 LTS (Free tier eligible)
4. **Instance Type:** 
   - t3.small (2 vCPU, 2GB) - ₹1,200/month - Good for starting
   - t3.medium (2 vCPU, 4GB) - ₹2,500/month - Better performance
5. **Key Pair:** Create new → Download .pem file (SAVE THIS SECURELY!)
6. **Security Group:** Create new with these rules:

| Type | Port | Source |
|------|------|--------|
| SSH | 22 | Your IP |
| HTTP | 80 | 0.0.0.0/0 |
| HTTPS | 443 | 0.0.0.0/0 |

7. **Storage:** 30 GB gp3 (SSD)
8. Launch!

### 3.2 Allocate Elastic IP (Static IP)
1. EC2 → Elastic IPs → Allocate
2. Associate with your instance
3. **Note this IP** - you'll use it for DNS

---

## STEP 4: Connect to EC2 & Install Docker

### 4.1 Connect via SSH
```bash
# On Windows (use Git Bash or WSL)
chmod 400 your-key.pem
ssh -i your-key.pem ubuntu@YOUR_ELASTIC_IP

# On Windows PowerShell
ssh -i your-key.pem ubuntu@YOUR_ELASTIC_IP
```

### 4.2 Install Docker & Docker Compose
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker ubuntu

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Logout and login again for group changes
exit
# Then SSH back in
```

### 4.3 Verify Installation
```bash
docker --version
docker compose version
```

---

## STEP 5: Setup RDS PostgreSQL (Optional but Recommended)

Using RDS instead of Docker PostgreSQL provides better reliability.

### 5.1 Create RDS Instance
1. Go to RDS → Create Database
2. **Engine:** PostgreSQL 15
3. **Template:** Free tier (or Production)
4. **DB Instance Identifier:** hamsvic-db
5. **Master Username:** hamsvic_admin
6. **Master Password:** (generate strong password - SAVE IT!)
7. **Instance:** db.t3.micro (free tier) or db.t3.small
8. **Storage:** 20 GB gp2
9. **VPC:** Default
10. **Public Access:** No (for security)
11. **Security Group:** Create new, allow port 5432 from EC2 security group

### 5.2 Note Connection Details
- Endpoint: `hamsvic-db.xxxxx.us-east-1.rds.amazonaws.com`
- Port: 5432
- Database: postgres (create your database after)

---

## STEP 6: Setup S3 for Media Files

### 6.1 Create S3 Bucket
1. Go to S3 → Create Bucket
2. **Bucket Name:** hamsvic-media-production
3. **Region:** Same as EC2 (e.g., ap-south-1 for Mumbai)
4. **Block Public Access:** Uncheck (for media files)
5. Create!

### 6.2 Create IAM User for S3
1. IAM → Users → Create User
2. **Name:** hamsvic-s3-user
3. Attach Policy: AmazonS3FullAccess
4. Create Access Key → Save Access Key ID & Secret

### 6.3 Bucket Policy (for public read)
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::hamsvic-media-production/*"
        }
    ]
}
```

---

## STEP 7: Razorpay Setup

### 7.1 Create Razorpay Account
1. Go to https://razorpay.com
2. Click "Sign Up"
3. Enter business details:
   - Business Name
   - Business Type: Proprietorship/Partnership/Company
   - PAN Card
   - GST Number (optional)
   - Bank Account Details

### 7.2 Complete KYC
1. Upload documents:
   - PAN Card
   - Address Proof
   - Business Registration (if applicable)
   - Bank Statement/Cancelled Cheque
2. Wait for verification (usually 1-2 business days)

### 7.3 Get API Keys
1. Go to Settings → API Keys
2. Generate Keys
3. **Test Mode Keys:** Use for development
4. **Live Mode Keys:** Use for production

```
Key ID: rzp_live_xxxxxxxxxxxxxxx
Key Secret: xxxxxxxxxxxxxxxxxxxxxxxx
```

### 7.4 Configure Webhooks
1. Settings → Webhooks → Add New Webhook
2. **URL:** https://yourdomain.com/api/razorpay/webhook/
3. **Secret:** Generate and save
4. **Events:** Select all payment events

---

## STEP 8: Domain DNS Configuration

### 8.1 Point Domain to AWS
In your domain registrar (GoDaddy/Namecheap):

1. Go to DNS Management
2. Add/Edit these records:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | @ | YOUR_ELASTIC_IP | 600 |
| A | www | YOUR_ELASTIC_IP | 600 |
| CNAME | api | YOUR_ELASTIC_IP | 600 |

### 8.2 Wait for Propagation
DNS changes take 5-30 minutes (sometimes up to 48 hours)

Check: https://dnschecker.org

---

## STEP 9: Deploy Application

### 9.1 Upload Code to Server
```bash
# On your local machine (Git Bash/PowerShell)
cd "H:\Version 3\Windows x 1"

# Create a zip of your project
# Or use Git:
git init
git add .
git commit -m "Production deploy"

# Push to GitHub (create private repo first)
git remote add origin https://github.com/yourusername/hamsvic.git
git push -u origin main
```

### 9.2 On EC2 Server
```bash
# Clone your repo
cd ~
git clone https://github.com/yourusername/hamsvic.git
cd hamsvic

# Or upload via SCP
# scp -i your-key.pem -r "H:\Version 3\Windows x 1\*" ubuntu@YOUR_IP:~/hamsvic/
```

### 9.3 Create Environment File
```bash
nano .env
```

Add these contents:
```env
# Django Settings
DEBUG=False
SECRET_KEY=your-super-secret-key-generate-new-one
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,YOUR_ELASTIC_IP

# Database (RDS)
DB_NAME=hamsvic_production
DB_USER=hamsvic_admin
DB_PASSWORD=your-rds-password
DB_HOST=hamsvic-db.xxxxx.rds.amazonaws.com
DB_PORT=5432

# Redis
REDIS_URL=redis://redis:6379/0

# AWS S3
AWS_ACCESS_KEY_ID=your-s3-access-key
AWS_SECRET_ACCESS_KEY=your-s3-secret-key
AWS_STORAGE_BUCKET_NAME=hamsvic-media-production
AWS_S3_REGION_NAME=ap-south-1

# Razorpay
RAZORPAY_KEY_ID=rzp_live_xxxxxxxxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
RAZORPAY_WEBHOOK_SECRET=your-webhook-secret

# Email (Optional - use SendGrid/SES)
EMAIL_HOST=smtp.sendgrid.net
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=your-sendgrid-api-key
EMAIL_PORT=587

# Sentry (Optional - Error Tracking)
SENTRY_DSN=https://xxx@sentry.io/xxx
```

### 9.4 Launch with Docker Compose
```bash
# Build and start
docker compose -f docker-compose.production.yml up -d --build

# Check logs
docker compose -f docker-compose.production.yml logs -f

# Run migrations
docker compose -f docker-compose.production.yml exec web python manage.py migrate

# Create superuser
docker compose -f docker-compose.production.yml exec web python manage.py createsuperuser
```

---

## STEP 10: Setup Nginx & SSL

### 10.1 Install Nginx on EC2
```bash
sudo apt install nginx -y
sudo systemctl enable nginx
```

### 10.2 Configure Nginx
```bash
sudo nano /etc/nginx/sites-available/hamsvic
```

```nginx
upstream django {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location / {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /home/ubuntu/hamsvic/staticfiles/;
    }

    client_max_body_size 50M;
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/hamsvic /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 10.3 Install SSL with Let's Encrypt (FREE)
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Get SSL certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renewal (already set up by certbot)
sudo certbot renew --dry-run
```

---

## STEP 11: Setup Email (SendGrid - Free Tier)

### 11.1 Create SendGrid Account
1. Go to https://sendgrid.com
2. Sign up (Free: 100 emails/day)
3. Create API Key: Settings → API Keys → Create

### 11.2 Update .env
```env
EMAIL_HOST=smtp.sendgrid.net
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=SG.xxxxxxxxxxxxxxxxxxxxxxxx
EMAIL_PORT=587
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
```

---

## STEP 12: Monitoring & Maintenance

### 12.1 Setup CloudWatch (AWS Monitoring)
1. EC2 → Select Instance → Monitoring tab
2. Enable detailed monitoring

### 12.2 Setup Sentry (Error Tracking - Free Tier)
1. Go to https://sentry.io
2. Create account and project
3. Add DSN to .env

### 12.3 Backup Strategy
```bash
# Database backup (add to cron)
docker compose -f docker-compose.production.yml exec postgres pg_dump -U hamsvic hamsvic_production > backup_$(date +%Y%m%d).sql

# Upload to S3
aws s3 cp backup_$(date +%Y%m%d).sql s3://hamsvic-backups/
```

---

## Cost Summary

| Service | Monthly Cost (INR) |
|---------|-------------------|
| EC2 t3.small | ₹1,200-1,500 |
| RDS db.t3.micro | ₹1,200-1,500 |
| S3 (50GB) | ₹150-300 |
| Data Transfer | ₹500-1,000 |
| Domain | ₹80/month (yearly) |
| SSL | FREE |
| SendGrid | FREE (100/day) |
| Razorpay | 2% per transaction |
| **TOTAL** | **₹3,000-4,500/month** |

---

## Quick Commands Reference

```bash
# SSH to server
ssh -i key.pem ubuntu@YOUR_IP

# View logs
docker compose -f docker-compose.production.yml logs -f web

# Restart services
docker compose -f docker-compose.production.yml restart

# Update code
git pull origin main
docker compose -f docker-compose.production.yml up -d --build

# Database shell
docker compose -f docker-compose.production.yml exec postgres psql -U hamsvic hamsvic_production

# Django shell
docker compose -f docker-compose.production.yml exec web python manage.py shell
```

---

## Checklist Before Going Live

- [ ] Domain purchased and DNS configured
- [ ] AWS account with MFA enabled
- [ ] EC2 instance running with Elastic IP
- [ ] RDS database created (or using Docker PostgreSQL)
- [ ] S3 bucket for media files
- [ ] Razorpay account verified with live keys
- [ ] SSL certificate installed
- [ ] Email service configured
- [ ] Superuser account created
- [ ] Test all payment flows
- [ ] Backup strategy in place

---

## Need Help?

If you get stuck at any step, share the error message and I'll help you resolve it!
