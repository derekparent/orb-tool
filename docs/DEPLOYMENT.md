# Deployment Guide

This guide covers deploying the Oil Record Book Tool to production.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start (Docker)](#quick-start-docker)
- [Configuration](#configuration)
- [Docker Deployment](#docker-deployment)
- [Manual Deployment](#manual-deployment)
- [Database Management](#database-management)
- [SSL/HTTPS Setup](#sslhttps-setup)
- [Monitoring](#monitoring)
- [Backup Strategy](#backup-strategy)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

- Docker 20.10+ and Docker Compose 2.0+ (for Docker deployment)
- Python 3.11+ (for manual deployment)
- 512MB RAM minimum (1GB recommended)
- 1GB disk space

## Quick Start (Docker)

```bash
# 1. Clone the repository
git clone git@github.com:derekparent/orb-tool.git
cd orb-tool

# 2. Create environment file
cp .env.example .env

# 3. Generate a secure secret key
python -c "import secrets; print(secrets.token_hex(32))"
# Add the output to SECRET_KEY in .env

# 4. Build and start
docker compose up -d

# 5. Initialize the database
docker compose exec web flask db upgrade

# 6. Create admin user
docker compose exec web python create_admin_user.py

# 7. Access at http://localhost:8000
```

## Configuration

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Flask session signing key | `a1b2c3...` (64 hex chars) |

### Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_ENV` | `production` | Environment mode |
| `PORT` | `8000` | Server port |
| `DATABASE_URL` | `sqlite:///data/orb.db` | Database connection string |
| `CORS_ORIGINS` | `http://localhost:8000` | Allowed CORS origins |
| `SESSION_SECURE` | `true` | Secure cookie flag |
| `REDIS_URL` | `memory://` | Rate limit storage |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `GOOGLE_APPLICATION_CREDENTIALS` | - | Path to GCP service account JSON |

### Generating Secret Key

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**Never** commit your secret key to version control.

## Docker Deployment

### Building the Image

```bash
# Build production image
docker build -t orb-tool:latest .

# Build with specific tag
docker build -t orb-tool:v1.0.0 .
```

### Running with Docker Compose

```bash
# Start in detached mode
docker compose up -d

# View logs
docker compose logs -f web

# Stop
docker compose down

# Stop and remove volumes (WARNING: deletes data)
docker compose down -v
```

### Using Redis for Rate Limiting

For production with multiple workers:

```bash
# Enable Redis profile
docker compose --profile with-redis up -d

# Update .env
REDIS_URL=redis://redis:6379/0
```

### Container Health

The container includes a health check that verifies:
- Application is responding on `/health`
- Database connection is working

```bash
# Check container health
docker inspect --format='{{.State.Health.Status}}' orb-tool
```

## Manual Deployment

### System Setup

```bash
# Create application user
sudo useradd -m -s /bin/bash orb
sudo su - orb

# Clone repository
git clone git@github.com:derekparent/orb-tool.git
cd orb-tool

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Systemd Service

Create `/etc/systemd/system/orb-tool.service`:

```ini
[Unit]
Description=Oil Record Book Tool
After=network.target

[Service]
User=orb
Group=orb
WorkingDirectory=/home/orb/orb-tool
Environment="PATH=/home/orb/orb-tool/venv/bin"
EnvironmentFile=/home/orb/orb-tool/.env
ExecStart=/home/orb/orb-tool/venv/bin/gunicorn --config gunicorn.conf.py src.app:create_app()
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable orb-tool
sudo systemctl start orb-tool

# Check status
sudo systemctl status orb-tool
```

## Database Management

### Running Migrations

```bash
# Docker
docker compose exec web flask db upgrade

# Manual
flask db upgrade
```

### Creating Backups

```bash
# Docker - copy database out of container
docker compose exec web python scripts/backup_database.py
docker cp orb-tool:/app/data/backups ./backups

# Manual
python scripts/backup_database.py
```

### Restoring from Backup

```bash
# Docker
docker cp ./backups/orb.db.backup-TIMESTAMP orb-tool:/app/data/
docker compose exec web python scripts/restore_database.py orb.db.backup-TIMESTAMP

# Manual
python scripts/restore_database.py data/backups/orb.db.backup-TIMESTAMP
```

## SSL/HTTPS Setup

### Using Nginx as Reverse Proxy

Install Nginx and create `/etc/nginx/sites-available/orb-tool`:

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static files (optional optimization)
    location /static/ {
        alias /home/orb/orb-tool/static/;
        expires 30d;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/orb-tool /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Get SSL certificate with Certbot
sudo certbot --nginx -d yourdomain.com
```

### Update Environment for HTTPS

```bash
# .env
SESSION_SECURE=true
CORS_ORIGINS=https://yourdomain.com
```

## Monitoring

### Health Check Endpoint

```bash
curl http://localhost:8000/health
# {"status": "healthy", "database": "connected", "version": "1.0.0"}
```

### Logs

```bash
# Docker
docker compose logs -f web

# Systemd
sudo journalctl -u orb-tool -f
```

### Gunicorn Metrics

Access logs include response time in microseconds:
```
192.168.1.1 - - [28/Dec/2025:12:00:00 +0000] "GET /api/dashboard/full HTTP/1.1" 200 1234 "-" "Mozilla/5.0" 45000
```

The last number (45000) is response time in μs (45ms).

## Backup Strategy

### Recommended Schedule

| Backup Type | Frequency | Retention |
|-------------|-----------|-----------|
| Full database | Daily | 30 days |
| Before migration | Always | Permanent |
| Before hitch end | Always | Permanent |

### Automated Backup (Cron)

```bash
# Add to crontab
0 2 * * * /home/orb/orb-tool/venv/bin/python /home/orb/orb-tool/scripts/backup_database.py
```

### Off-site Backup

```bash
# Sync to cloud storage (example with rclone)
rclone sync /home/orb/orb-tool/data/backups remote:orb-backups
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose logs web

# Common issues:
# - SECRET_KEY not set
# - Port already in use
# - Volume permissions
```

### Database Locked

SQLite can lock during concurrent writes. Solutions:
1. Ensure only one write operation at a time
2. Consider PostgreSQL for high-concurrency scenarios

```bash
# Check for locks
fuser data/orb.db
```

### Health Check Failing

```bash
# Test manually
curl -v http://localhost:8000/health

# Check database
docker compose exec web python -c "from src.models import db; from src.app import create_app; app = create_app(); app.app_context().push(); print(db.engine.execute('SELECT 1').fetchone())"
```

### Permission Denied

```bash
# Fix volume permissions (Docker)
docker compose exec web chown -R appuser:appgroup /app/data

# Fix file permissions (manual)
chown -R orb:orb /home/orb/orb-tool/data
chmod 755 /home/orb/orb-tool/data
```

### OCR Not Working

1. Verify Google Cloud credentials are mounted
2. Check service account has Vision API access
3. Verify `GOOGLE_APPLICATION_CREDENTIALS` path

```bash
docker compose exec web python -c "from google.cloud import vision; client = vision.ImageAnnotatorClient(); print('OK')"
```

---

## Platform-Specific Guides

### Railway

```bash
# railway.json is auto-detected, or use:
railway up
```

### Fly.io

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Launch
fly launch
fly secrets set SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
fly deploy
```

### Heroku

```bash
# Create Procfile
echo "web: gunicorn --config gunicorn.conf.py src.app:create_app()" > Procfile

# Deploy
heroku create orb-tool
heroku config:set SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
git push heroku main
```

---

## Security Checklist

- [ ] Strong SECRET_KEY generated and not in version control
- [ ] SESSION_SECURE=true when using HTTPS
- [ ] CORS_ORIGINS restricted to your domain
- [ ] Firewall configured (only ports 80, 443 exposed)
- [ ] Database file permissions restricted (600)
- [ ] Regular backups configured and tested
- [ ] SSL/TLS configured with modern ciphers
- [ ] Rate limiting enabled
- [ ] Admin account password changed from default
