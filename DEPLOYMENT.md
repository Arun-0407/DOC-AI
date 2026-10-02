# Deployment Guide

## Production Deployment

### 1. Server Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 4 GB | 8+ GB |
| Disk | 20 GB | 50+ GB SSD |
| OS | Ubuntu 22.04+ | Ubuntu 24.04 LTS |

### 2. Domain & SSL Setup

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d yourdomain.com
```

### 3. Environment Setup

```bash
# Clone repository
git clone <repo-url> /opt/docai
cd /opt/docai

# Create production .env
cp .env.example .env
nano .env
# Set:
# - Strong JWT_SECRET (use: openssl rand -hex 32)
# - Real OPENAI_API_KEY
# - Production DATABASE_URL
# - CORS_ORIGINS with your domain
```

### 4. Docker Production Deployment

```bash
# Build and start
docker-compose -f docker-compose.yml up -d --build

# Check status
docker-compose ps

# View logs
docker-compose logs -f backend
```

### 5. Nginx Reverse Proxy

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 50M;
    }
}
```

### 6. Database Backup

```bash
# Automated daily backup
0 2 * * * docker exec docai-db pg_dump -U docai docai_db | gzip > /backups/docai_$(date +\%Y\%m\%d).sql.gz
```

### 7. Monitoring

```bash
# Health check
curl http://localhost:8000/api/health

# Docker resource usage
docker stats
```

### 8. Scaling

For high-traffic deployments:

1. **Horizontal scaling**: Run multiple backend containers behind a load balancer
2. **Database**: Use managed PostgreSQL (AWS RDS, Azure PostgreSQL)
3. **File storage**: Use S3/Azure Blob for uploads
4. **Caching**: Add Redis for session and AI response caching
5. **CDN**: Use CloudFront/Azure CDN for frontend assets
