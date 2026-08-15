# 🐳 celia.pro Docker Setup Guide

**Version:** 3.2.0  
**Last Updated:** 2026-08-15

---

## 📋 Overview

This guide covers the complete Docker setup for celia.pro, including:

- **Production deployment** (`docker-compose.yml`)
- **Development environment** (`docker-compose.dev.yml`)
- **Monitoring stack** (Prometheus + Grafana)
- **Deployment scripts** for automated setup

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Compose                        │
│                                                          │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │   Frontend   │───▶│   Backend    │                   │
│  │  (Nginx:80)  │    │ (FastAPI:8K) │                   │
│  │  Port: 3000  │    │  Port: 8000  │                   │
│  └──────────────┘    └──────┬───────┘                   │
│                             │                            │
│                ┌────────────┼────────────┐               │
│                ▼            ▼            ▼               │
│          ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│          │ Postgres │ │  Redis   │ │Prometheus│        │
│          │  (5432)  │ │  (6379)  │ │  (9090)  │        │
│          └──────────┘ └──────────┘ └──────────┘        │
│                                                          │
│          ┌──────────────────────────────┐               │
│          │         Grafana              │               │
│          │        (Port 3001)           │               │
│          └──────────────────────────────┘               │
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Production (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/your-username/celia-pro.git
cd celia-pro

# 2. Run setup script (handles everything)
./scripts/setup.sh

# 3. Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Manual Setup

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Edit .env with your secrets
# Generate JWT secret: openssl rand -hex 32
nano .env

# 3. Build and start
docker compose up -d --build

# 4. Check status
docker compose ps

# 5. View logs
docker compose logs -f
```

### With Monitoring Stack

```bash
# Start with Prometheus + Grafana
docker compose --profile monitoring up -d

# Access monitoring
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3001 (admin/admin)
```

---

## 🛠️ Development Mode

For local development with hot-reload:

```bash
# Start development environment
./scripts/dev.sh

# Or manually:
docker compose -f docker-compose.dev.yml up --build
```

### Development Features:
- ✅ Backend hot-reload (auto-restart on code changes)
- ✅ Frontend hot-reload (Vite dev server)
- ✅ PostgreSQL with persistent data
- ✅ `AUTH_REQUIRED=false` (no auth needed for dev)
- ✅ Debug logging enabled

### Access in Development:
- Frontend: http://localhost:5173 (Vite dev server)
- Backend: http://localhost:8000
- Database: localhost:5432

---

## 📦 Container Details

### Backend (FastAPI)
- **Image:** `python:3.13-slim`
- **Port:** 8000
- **Workers:** 4 (configurable via `UVICORN_WORKERS`)
- **Health Check:** `/api/health`
- **User:** Non-root (celia:1001)

### Frontend (Nginx + React)
- **Image:** `nginx:1.27-alpine`
- **Port:** 80 (mapped to 3000)
- **Health Check:** `/`
- **Optimized:** Gzip, long-term caching for hashed assets
- **Code Splitting:** Supports lazy-loaded chunks

### PostgreSQL
- **Image:** `postgres:16-alpine`
- **Port:** 5432
- **Volume:** Persistent data storage
- **Health Check:** `pg_isready`

### Redis
- **Image:** `redis:7-alpine`
- **Port:** 6379
- **Authentication:** Password-protected
- **Health Check:** `redis-cli ping`

### Prometheus (Optional)
- **Image:** `prom/prometheus:v2.48.0`
- **Port:** 9090
- **Scrape Interval:** 10s
- **Retention:** 7 days

### Grafana (Optional)
- **Image:** `grafana/grafana:10.2.0`
- **Port:** 3001
- **Default User:** admin / admin (change in production!)

---

## 🔧 Configuration

### Environment Variables

See `.env.example` for all available options.

**Critical Variables:**
```bash
# Authentication
JWT_SECRET_KEY=<generate-with-openssl-rand-hex-32>
AUTH_REQUIRED=true  # false only for development

# Database
POSTGRES_PASSWORD=<strong-password>
POSTGRES_DB=celia_db

# Redis
REDIS_PASSWORD=<strong-password>

# Monitoring (Optional)
SENTRY_DSN=<your-sentry-dsn>
LOG_LEVEL=INFO
LOG_FORMAT=json

# Performance
UVICORN_WORKERS=4  # Adjust based on CPU cores
```

### Generate Secrets

```bash
# JWT Secret
openssl rand -hex 32

# Database Password
openssl rand -hex 16

# Redis Password
openssl rand -hex 16
```

---

## 📊 Monitoring

### Prometheus Metrics

Backend exposes metrics at `/metrics` endpoint:

```bash
# View metrics
curl http://localhost:8000/metrics

# Custom metrics include:
# - novamind_llm_requests_total
# - novamind_llm_request_duration_seconds
# - novamind_tool_executions_total
# - novamind_active_users
# - novamind_conversations_total
# - novamind_messages_total
# - novamind_errors_total
# - novamind_circuit_breaker_state
```

### Grafana Dashboards

1. Access Grafana: http://localhost:3001
2. Login with admin credentials
3. Prometheus datasource is auto-configured
4. Create dashboards using the metrics above

### Production Security

**⚠️ Restrict `/metrics` endpoint in production:**

Edit `docker/nginx.conf` and uncomment:

```nginx
location /metrics {
    allow 10.0.0.0/8;  # Your monitoring IPs
    allow 172.16.0.0/12;
    deny all;
    proxy_pass http://backend;
}
```

---

## 🔄 Common Operations

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f frontend

# Last 100 lines
docker compose logs --tail=100 backend
```

### Restart Services

```bash
# Restart all
docker compose restart

# Restart specific service
docker compose restart backend

# Rebuild and restart (after code changes)
docker compose up -d --build
```

### Database Operations

```bash
# Access PostgreSQL shell
docker compose exec postgres psql -U celia -d celia_db

# Run migrations
docker compose exec backend alembic upgrade head

# Reset database (⚠️ DELETES ALL DATA)
docker compose down -v
docker compose up -d
```

### Backup & Restore

```bash
# Backup database
docker compose exec postgres pg_dump -U celia celia_db > backup.sql

# Restore database
cat backup.sql | docker compose exec -T postgres psql -U celia -d celia_db
```

### Stop & Cleanup

```bash
# Stop all services
docker compose down

# Stop and remove volumes (⚠️ DELETES DATA)
docker compose down -v

# Stop and remove images
docker compose down --rmi all
```

---

## 🚢 Production Deployment

### Using Deployment Script

```bash
# Automated production deployment
./scripts/deploy.sh

# With monitoring stack
./scripts/deploy.sh --with-monitoring
```

### Manual Production Deployment

```bash
# 1. Ensure .env is configured
cp .env.example .env
nano .env

# 2. Build production images
docker compose build --no-cache

# 3. Start services
docker compose up -d

# 4. Run migrations
docker compose exec backend alembic upgrade head

# 5. Verify health
curl http://localhost:8000/api/health
curl http://localhost:3000
```

### Reverse Proxy (Nginx/Traefik)

For production with custom domain, use a reverse proxy:

**Example Nginx config:**

```nginx
server {
    listen 443 ssl http2;
    server_name celia.pro;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ws/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
    }
}
```

---

## 🐛 Troubleshooting

### Backend won't start

```bash
# Check logs
docker compose logs backend

# Common issues:
# 1. Database not ready - wait for postgres health check
# 2. Missing env vars - check .env file
# 3. Port already in use - change BACKEND_PORT in .env
```

### Frontend shows blank page

```bash
# Check if backend is running
docker compose ps

# Check nginx config
docker compose exec frontend nginx -t

# Rebuild frontend
docker compose build frontend
docker compose restart frontend
```

### Database connection errors

```bash
# Check postgres health
docker compose exec postgres pg_isready

# Check connection string in .env
# Format: postgresql+asyncpg://user:password@postgres:5432/dbname
```

### Performance issues

```bash
# Increase workers
echo "UVICORN_WORKERS=8" >> .env
docker compose restart backend

# Check resource usage
docker stats
```

---

## 📚 Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)

---

## 🤝 Support

For issues and questions:
- GitHub Issues: https://github.com/your-username/celia-pro/issues
- Documentation: See `README.md` and `API_DOCUMENTATION.md`

---

**Built with ❤️ for production excellence.**
