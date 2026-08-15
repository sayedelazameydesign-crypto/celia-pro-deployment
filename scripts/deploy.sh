#!/bin/bash
# celia.pro - Production Deployment Script
# Usage: ./scripts/deploy.sh [--with-monitoring]
set -euo pipefail

echo "╔══════════════════════════════════════════════════╗"
echo "║     🚀 celia.pro Production Deployment v3.2.0    ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

MONITORING=false
for arg in "$@"; do
    case $arg in
        --with-monitoring)
            MONITORING=true
            shift
            ;;
    esac
done

# ============= VALIDATE ENVIRONMENT =============
echo -e "${YELLOW}[1/5] Validating environment...${NC}"

if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Run: cp .env.example .env && edit .env"
    exit 1
fi

# Check critical environment variables
check_env() {
    local var=$1
    local value="${!var:-}"
    if [ -z "$value" ] || [[ "$value" == *"CHANGE_THIS"* ]]; then
        echo -e "${RED}Error: $var is not set in .env${NC}"
        exit 1
    fi
}

check_env "JWT_SECRET_KEY"
check_env "POSTGRES_PASSWORD"
check_env "REDIS_PASSWORD"

echo -e "${GREEN}  ✓ Environment validated${NC}"

# ============= BUILD =============
echo ""
echo -e "${YELLOW}[2/5] Building production images...${NC}"
docker compose build --no-cache 2>/dev/null || docker compose build
echo -e "${GREEN}  ✓ Images built${NC}"

# ============= STOP OLD SERVICES =============
echo ""
echo -e "${YELLOW}[3/5] Stopping old services...${NC}"
docker compose down --remove-orphans 2>/dev/null || true
echo -e "${GREEN}  ✓ Old services stopped${NC}"

# ============= START NEW SERVICES =============
echo ""
echo -e "${YELLOW}[4/5] Starting production services...${NC}"

if [ "$MONITORING" = true ]; then
    echo "  Starting with monitoring stack (Prometheus + Grafana)..."
    docker compose --profile monitoring up -d
else
    docker compose up -d
fi

echo -e "${GREEN}  ✓ Services started${NC}"

# ============= HEALTH CHECKS =============
echo ""
echo -e "${YELLOW}[5/5] Running health checks...${NC}"

sleep 10

# Check backend health
BACKEND_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health 2>/dev/null || echo "000")
if [ "$BACKEND_HEALTH" = "200" ]; then
    echo -e "${GREEN}  ✓ Backend: healthy (HTTP $BACKEND_HEALTH)${NC}"
else
    echo -e "${YELLOW}  ! Backend: checking... (HTTP $BACKEND_HEALTH)${NC}"
fi

# Check frontend
FRONTEND_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 2>/dev/null || echo "000")
if [ "$FRONTEND_HEALTH" = "200" ]; then
    echo -e "${GREEN}  ✓ Frontend: healthy (HTTP $FRONTEND_HEALTH)${NC}"
else
    echo -e "${YELLOW}  ! Frontend: checking... (HTTP $FRONTEND_HEALTH)${NC}"
fi

# ============= DEPLOYMENT SUMMARY =============
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo -e "║        ${GREEN}✅ Deployment Complete!${NC}                 ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║                                                  ║"
echo "║  🌐 Frontend:  http://localhost:3000             ║"
echo "║  🔧 Backend:   http://localhost:8000             ║"
echo "║  📊 Metrics:   http://localhost:8000/metrics     ║"

if [ "$MONITORING" = true ]; then
    echo "║                                                  ║"
    echo "║  📈 Prometheus: http://localhost:9090            ║"
    echo "║  📉 Grafana:    http://localhost:3001            ║"
fi

echo "║                                                  ║"
echo "║  📖 Logs:     docker compose logs -f             ║"
echo "║  🛑 Stop:     docker compose down                ║"
echo "║  🔄 Restart:  docker compose restart             ║"
echo "║                                                  ║"
echo "╚══════════════════════════════════════════════════╝"
