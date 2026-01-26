# ==============================================================================
# HAMSVIC - AWS INFRASTRUCTURE SETUP GUIDE
# ==============================================================================

## 🏗️ AWS Services You Need

| Service | Purpose | Estimated Cost/Month |
|---------|---------|---------------------|
| EC2 (t3.small) | Application Server | ~$15-20 |
| RDS (db.t3.micro PostgreSQL) | Database | ~$15-25 |
| ElastiCache (cache.t3.micro) | Redis for caching | ~$12-15 |
| S3 | File storage | ~$2-5 |
| Route 53 | Domain DNS | ~$0.50 |
| ACM | SSL Certificate | FREE |
| SES | Email (OTP) | ~$1-2 |
| **Total** | | **~$45-70/month** |

---

## 📋 STEP-BY-STEP SETUP

### Step 1: Create VPC & Security Groups

1. Go to **VPC Console** → Create VPC
   - Name: `hamsvic-vpc`
   - CIDR: `10.0.0.0/16`
   
2. Create **Security Groups**:

   **sg-web** (for EC2):
   - Inbound: 22 (SSH), 80 (HTTP), 443 (HTTPS)
   - Outbound: All
   
   **sg-database** (for RDS):
   - Inbound: 5432 from sg-web only
   
   **sg-cache** (for ElastiCache):
   - Inbound: 6379 from sg-web only

---

### Step 2: Create RDS PostgreSQL Database

1. Go to **RDS Console** → Create Database
2. Settings:
   - Engine: PostgreSQL 15
   - Template: Free tier (for testing) or Production
   - DB Instance: `db.t3.micro` (start small, scale later)
   - Storage: 20 GB gp3
   - DB Name: `hamsvic_production`
   - Master username: `hamsvic_admin`
   - Master password: (save this securely!)
   - VPC: `hamsvic-vpc`
   - Security Group: `sg-database`
   - Public access: No

3. Note down the **Endpoint** (e.g., `hamsvic-db.xxxxx.ap-south-1.rds.amazonaws.com`)

---

### Step 3: Create ElastiCache Redis

1. Go to **ElastiCache Console** → Create Redis Cluster
2. Settings:
   - Cluster mode: Disabled
   - Node type: `cache.t3.micro`
   - Number of replicas: 0 (for cost savings)
   - VPC: `hamsvic-vpc`
   - Security Group: `sg-cache`

3. Note down the **Primary Endpoint**

---

### Step 4: Create S3 Bucket

1. Go to **S3 Console** → Create Bucket
2. Settings:
   - Bucket name: `hamsvic-production-files` (must be globally unique)
   - Region: `ap-south-1` (Mumbai)
   - Block public access: Keep ON (we use signed URLs)
   - Versioning: Enable (for file recovery)

3. Create **IAM User** for S3 access:
   - Go to IAM → Users → Create User
   - Name: `hamsvic-s3-user`
   - Attach policy: Create custom policy:
   
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::hamsvic-production-files",
                "arn:aws:s3:::hamsvic-production-files/*"
            ]
        }
    ]
}
```

4. Create **Access Keys** and save them securely

---

### Step 5: Create EC2 Instance

1. Go to **EC2 Console** → Launch Instance
2. Settings:
   - AMI: Ubuntu 22.04 LTS
   - Instance type: `t3.small` (2 vCPU, 2 GB RAM)
   - Key pair: Create new or use existing
   - VPC: `hamsvic-vpc`
   - Security Group: `sg-web`
   - Storage: 30 GB gp3

3. Allocate **Elastic IP** and associate with instance

---

### Step 6: Setup Domain & SSL

1. **Route 53**:
   - Create Hosted Zone for your domain
   - Add A record pointing to EC2 Elastic IP
   - Add CNAME for www

2. **SSL Certificate**:
   - The deploy.sh script uses Let's Encrypt (free)
   - Alternatively, use ACM for AWS-managed certificates

---

### Step 7: Setup SES for Email

1. Go to **SES Console** → Verified identities
2. Verify your domain (add DNS records)
3. Create **SMTP credentials**
4. Request **production access** (to send to any email)

---

### Step 8: Deploy Application

1. SSH into EC2:
```bash
ssh -i your-key.pem ubuntu@your-elastic-ip
```

2. Upload your code:
```bash
# From your local machine:
scp -i your-key.pem -r "./Windows x 1/"* ubuntu@your-ip:~/hamsvic/
```

3. Create `.env` file:
```bash
cd ~/hamsvic
cp .env.production.example .env
nano .env  # Fill in all the values
```

4. Run deployment script:
```bash
chmod +x deploy/deploy.sh
sudo ./deploy/deploy.sh
```

---

## 🔒 SECURITY CHECKLIST

- [ ] RDS not publicly accessible
- [ ] ElastiCache not publicly accessible  
- [ ] S3 bucket blocks public access
- [ ] EC2 security group only allows 22, 80, 443
- [ ] Strong passwords for RDS and Django admin
- [ ] SSL certificate installed
- [ ] Django DEBUG=False in production
- [ ] ALLOWED_HOSTS properly configured
- [ ] Secrets stored in .env (not in code)

---

## 📊 MONITORING (Optional)

1. **CloudWatch** - Basic metrics (CPU, memory)
2. **Sentry** - Error tracking (free tier available)
3. **UptimeRobot** - Uptime monitoring (free)

---

## 💰 COST OPTIMIZATION TIPS

1. Use **Reserved Instances** for EC2/RDS (up to 40% savings)
2. Start with **t3.micro** and scale up as needed
3. Use **S3 Intelligent-Tiering** for old files
4. Set up **billing alerts** in AWS Console
5. Consider **Lightsail** for simpler, predictable pricing (~$20/month all-in-one)

---

## 🚀 QUICK START COMMANDS

```bash
# SSH to server
ssh -i key.pem ubuntu@your-ip

# Check application status
sudo systemctl status hamsvic

# View logs
sudo journalctl -u hamsvic -f

# Restart application
sudo systemctl restart hamsvic

# Django shell
cd ~/hamsvic && source venv/bin/activate && python manage.py shell

# Database migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```
