# Deployment Guide

Complete guide for deploying the Adaptive Deployment Orchestrator in production environments.

## Deployment Architecture Overview

```mermaid
graph TB
    subgraph "Internet"
        Users[Users]
        CICD[CI/CD Systems]
    end

    subgraph "Load Balancer"
        LB[Load Balancer / CDN]
    end

    subgraph "Application Tier"
        FE[Frontend<br/>React + Nginx]
        BE1[Backend API 1]
        BE2[Backend API 2]
        BE3[Backend API N]
    end

    subgraph "Data Tier"
        DB[(PostgreSQL)]
        Redis[(Redis Cache)]
    end

    subgraph "Monitoring"
        Prom[Prometheus]
        Grafana[Grafana]
    end

    Users --> LB
    CICD --> LB
    LB --> FE
    LB --> BE1 & BE2 & BE3
    BE1 & BE2 & BE3 --> DB
    BE1 & BE2 & BE3 --> Redis
    BE1 & BE2 & BE3 --> Prom
    Prom --> Grafana
```

## Prerequisites

- Docker 20.10+ and Docker Compose 2.0+
- PostgreSQL 15+ (or use Docker Compose)
- Python 3.11+ (for CLI)
- Node.js 18+ (for frontend development)
- Kubernetes 1.24+ (optional, for deployment targets)

## Quick Start with Docker Compose

The fastest way to get started is using Docker Compose:

```bash
# Clone the repository
git clone <repository-url>
cd adaptive-deployment-orchestrator

# Copy environment file
cp backend/.env.example backend/.env

# Generate a secure secret key
python3 -c "import secrets; print(secrets.token_urlsafe(32))" > .secret_key
SECRET_KEY=$(cat .secret_key)

# Update .env file with secret key
sed -i "s/your-secret-key-min-32-characters-change-this-in-production/$SECRET_KEY/" backend/.env

# Start all services
docker-compose up -d

# Check service health
docker-compose ps
```

### Service Architecture

```mermaid
graph LR
    subgraph "Docker Compose Stack"
        Frontend[Frontend:3000]
        Backend[Backend:8000]
        Postgres[(PostgreSQL:5432)]
        Prometheus[Prometheus:9090]
        Grafana[Grafana:3001]
    end
    
    Frontend --> Backend
    Backend --> Postgres
    Backend --> Prometheus
    Prometheus --> Grafana
```

### Access the Application

- **Dashboard**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **API Health**: http://localhost:8000/health
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3001 (admin/admin)

### Default Credentials

**Important**: Change these in production!

- **Username**: admin
- **Password**: admin123

## Production Deployment

### 1. Environment Configuration

Create a production `.env` file:

```bash
# Application
APP_NAME="Adaptive Deployment Orchestrator"
ENVIRONMENT=production
DEBUG=false

# Security - CRITICAL: Change these!
SECRET_KEY=<generate-secure-32-char-key>
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Database
DATABASE_URL=postgresql+asyncpg://user:password@db-host:5432/ado_db
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40

# CORS Origins (your frontend URLs)
CORS_ORIGINS=https://dashboard.example.com,https://example.com

# Prometheus
PROMETHEUS_URL=http://prometheus:9090
PROMETHEUS_ENABLED=true

# Kubernetes Integration
K8S_ENABLED=true
K8S_NAMESPACE=default

# Observability
LOG_LEVEL=INFO
LOG_FORMAT=json
OTEL_ENABLED=true
```

### 2. Database Setup

#### Option A: Managed PostgreSQL

Use a managed database service (AWS RDS, Google Cloud SQL, etc.):

```bash
# Create database
psql -h <db-host> -U <admin-user> -c "CREATE DATABASE ado_db;"

# Create user
psql -h <db-host> -U <admin-user> -c "CREATE USER ado_user WITH PASSWORD 'secure-password';"
psql -h <db-host> -U <admin-user> -c "GRANT ALL PRIVILEGES ON DATABASE ado_db TO ado_user;"
```

#### Option B: Self-Hosted PostgreSQL

```bash
# Using Docker
docker run -d \
  --name ado-postgres \
  -e POSTGRES_USER=ado_user \
  -e POSTGRES_PASSWORD=secure-password \
  -e POSTGRES_DB=ado_db \
  -v postgres_data:/var/lib/postgresql/data \
  -p 5432:5432 \
  postgres:15-alpine
```

### 3. Backend Deployment

#### Using Docker

```bash
cd backend

# Build image
docker build -t ado-backend:latest .

# Run container
docker run -d \
  --name ado-backend \
  -p 8000:8000 \
  --env-file .env \
  ado-backend:latest
```

#### Using Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ado-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ado-backend
  template:
    metadata:
      labels:
        app: ado-backend
    spec:
      containers:
      - name: backend
        image: ado-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: ado-secrets
              key: database-url
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: ado-secrets
              key: secret-key
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /readiness
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
---
apiVersion: v1
kind: Service
metadata:
  name: ado-backend
spec:
  selector:
    app: ado-backend
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

### 4. Frontend Deployment

#### Build Production Assets

```bash
cd frontend

# Install dependencies
npm ci

# Build for production
npm run build

# Output is in dist/ directory
```

#### Deploy to Nginx

```bash
# Build Docker image
docker build -t ado-frontend:latest .

# Run container
docker run -d \
  --name ado-frontend \
  -p 80:80 \
  ado-frontend:latest
```

#### Deploy to CDN (Recommended)

For best performance, deploy to a CDN:

```bash
# Build
npm run build

# Deploy to S3 + CloudFront (AWS)
aws s3 sync dist/ s3://your-bucket-name/
aws cloudfront create-invalidation --distribution-id YOUR_DIST_ID --paths "/*"

# Or Vercel
vercel --prod

# Or Netlify
netlify deploy --prod
```

### 5. CLI Installation

#### From PyPI (when published)

```bash
pip install adaptive-deploy
```

#### From Source

```bash
cd cli
pip install -e .

# Verify installation
adaptive-deploy --help
```

#### Configure CLI

```bash
# Set API URL
export ADO_API_URL=https://api.example.com

# Login and get token
adaptive-deploy login --username admin --password <password>

# Export token for CI/CD
export ADO_TOKEN=<your-token>
```

## Monitoring Setup

### Prometheus Configuration

Create `monitoring/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'ado-backend'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/metrics'

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

rule_files:
  - 'alerts.yml'
```

### Grafana Dashboards

Import pre-built dashboards:

1. Access Grafana at http://localhost:3001
2. Go to Dashboards → Import
3. Import the dashboards from `monitoring/grafana/dashboards/`

**Available Dashboards**:
- Deployment Overview
- API Performance
- Database Metrics
- System Health

## Security Hardening

### 1. Environment Security

```bash
# Use secrets management
# AWS Secrets Manager
aws secretsmanager create-secret \
  --name ado/database-url \
  --secret-string "postgresql+asyncpg://..."

# Kubernetes Secrets
kubectl create secret generic ado-secrets \
  --from-literal=database-url='postgresql+asyncpg://...' \
  --from-literal=secret-key='...'
```

### 2. Network Security

- Use HTTPS/TLS in production
- Configure firewall rules
- Use VPN or private networks for database access
- Enable database SSL connections

### 3. Application Security

```bash
# Update SECRET_KEY to a strong random value
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Set secure CORS origins
CORS_ORIGINS=https://yourdomain.com

# Enable HTTPS only
# Use reverse proxy (Nginx, Traefik) with SSL certificates
```

### 4. Database Security

- Use strong passwords
- Enable SSL/TLS connections
- Restrict network access
- Regular backups
- Enable audit logging

## Backup and Recovery

### Database Backup

```bash
# Automated daily backups
0 2 * * * pg_dump -h localhost -U ado_user ado_db | gzip > /backups/ado_db_$(date +\%Y\%m\%d).sql.gz

# Restore from backup
gunzip -c backup.sql.gz | psql -h localhost -U ado_user ado_db
```

### Application State

- All deployment state is in PostgreSQL
- Audit logs provide full history
- Metrics are in Prometheus (configure retention)

## Scaling

### Horizontal Scaling

```bash
# Scale backend with Docker Compose
docker-compose up -d --scale backend=3

# Scale in Kubernetes
kubectl scale deployment ado-backend --replicas=5
```

### Load Balancing

Use a load balancer (Nginx, HAProxy, AWS ALB):

```nginx
upstream ado_backend {
    least_conn;
    server backend1:8000;
    server backend2:8000;
    server backend3:8000;
}

server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://ado_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Health Checks

### API Health Check

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### Readiness Check

```bash
curl http://localhost:8000/readiness
```

### Database Connectivity

```bash
psql -h localhost -U ado_user -d ado_db -c "SELECT 1;"
```

## Troubleshooting

### Backend Not Starting

```bash
# Check logs
docker logs ado-backend

# Common issues:
# 1. Database connection failed - verify DATABASE_URL
# 2. Secret key not set - check SECRET_KEY in .env
# 3. Port already in use - change PORT in .env
```

### Database Connection Issues

```bash
# Test connection
psql -h <db-host> -U ado_user -d ado_db

# Check firewall rules
telnet <db-host> 5432

# Verify credentials in .env
```

### Frontend Not Loading

```bash
# Check backend API
curl http://localhost:8000/health

# Check CORS configuration
# Ensure frontend URL is in CORS_ORIGINS

# Check browser console for errors
```

### WebSocket Connection Failed

```bash
# Verify WebSocket endpoint
wscat -c ws://localhost:8000/ws?token=<your-token>

# Check reverse proxy WebSocket support
# Ensure proxy_http_version 1.1 and upgrade headers
```

## Performance Tuning

### Database Optimization

```sql
-- Analyze tables
ANALYZE deployments;
ANALYZE deployment_history;
ANALYZE deployment_metrics;

-- Check query performance
EXPLAIN ANALYZE SELECT * FROM deployments WHERE status = 'in_progress';

-- Add indexes as needed
CREATE INDEX idx_custom ON table_name (column_name);
```

### Application Tuning

```python
# Adjust worker count based on CPU cores
# Rule of thumb: (2 x CPU cores) + 1
uvicorn app.main:app --workers 9 --host 0.0.0.0 --port 8000

# Adjust database pool size
DB_POOL_SIZE=30
DB_MAX_OVERFLOW=60
```

### Caching (Optional)

Add Redis for caching:

```python
# Cache deployment list for 30 seconds
@cache(ttl=30)
async def list_deployments():
    ...
```

## Migration Guide

### From Version 1.x to 2.x

```bash
# Backup database
pg_dump ado_db > backup.sql

# Run migrations
alembic upgrade head

# Restart services
docker-compose restart
```

## Support and Maintenance

### Monitoring Checklist

- [ ] API health endpoints responding
- [ ] Database connections healthy
- [ ] Deployment success rate > 95%
- [ ] API response time < 500ms P95
- [ ] Error rate < 1%
- [ ] Disk space > 20% free
- [ ] CPU usage < 70%
- [ ] Memory usage < 80%

### Regular Maintenance

- Weekly: Review logs for errors
- Weekly: Check disk space
- Monthly: Update dependencies
- Monthly: Review access logs
- Quarterly: Security audit
- Quarterly: Performance review

## Additional Resources

- [Architecture Guide](./ARCHITECTURE.md)
- [API Reference](./API.md)
- [CLI Reference](./CLI.md)
- [Security Best Practices](./SECURITY.md)
- [CI/CD Integration](./CICD.md)
