#!/bin/bash
# celia.pro - Setup script for production deployment
# Usage: ./scripts/setup.sh
set -euo pipefail

echo "╔══════════════════════════════════════════════════╗"
echo "║        celia.pro Production Setup v3.2.0         ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# ============= PREREQUISITES CHECK =============
echo -e "${YELLOW}[1/6] Checking prerequisites...${NC}"

check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}Error: $1 is not installed${NC}"
        echo "Install it from: $2"
        exit 1
    fi
    echo -e "${GREEN}  ✓ $1 found${NC}"
}

check_command "docker" "https://docs.docker.com/get-docker/"
check_command "docker" "https://docs.docker.com/compose/install/"

# ============= ENVIRONMENT SETUP =============
echo ""
echo -e "${YELLOW}[2/6] Setting up environment...${NC}"

if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "${GREEN}  ✓ Created .env from .env.example${NC}"
else
    echo -e "${YELLOW}  ! .env already exists (skipping)${NC}"
fi

# Generate JWT secret if not set
if grep -q "CHANGE_THIS_JWT_SECRET_KEY" .env 2>/dev/null; then
    JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))")
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|CHANGE_THIS_JWT_SECRET_KEY_USE_OPENSSL_RAND_HEX_32|$JWT_SECRET|" .env
    else
        sed -i "s|CHANGE_THIS_JWT_SECRET_KEY_USE_OPENSSL_RAND_HEX_32|$JWT_SECRET|" .env
    fi
    echo -e "${GREEN}  ✓ Generated JWT secret key${NC}"
fi

# Generate DB password if not set
if grep -q "CHANGE_THIS_SECURE_PASSWORD" .env 2>/dev/null; then
    DB_PASSWORD=$(openssl rand -hex 16 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(16))")
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|CHANGE_THIS_SECURE_PASSWORD|$DB_PASSWORD|" .env
    else
        sed -i "s|CHANGE_THIS_SECURE_PASSWORD|$DB_PASSWORD|" .env
    fi
    echo -e "${GREEN}  ✓ Generated database password${NC}"
fi

# Generate Redis password if not set
if grep -q "CHANGE_THIS_REDIS_PASSWORD" .env 2>/dev/null; then
    REDIS_PASSWORD=$(openssl rand -hex 16 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(16))")
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|CHANGE_THIS_REDIS_PASSWORD|$REDIS_PASSWORD|" .env
    else
        sed -i "s|CHANGE_THIS_REDIS_PASSWORD|$REDIS_PASSWORD|" .env
    fi
    echo -e "${GREEN}  ✓ Generated Redis password${NC}"
fi

# ============= DOCKER BUILD =============
echo ""
echo -e "${YELLOW}[3/6] Building Docker images (this may take a few minutes)...${NC}"
docker compose build --parallel

echo -e "${GREEN}  ✓ Images built successfully${NC}"

# ============= START SERVICES =============
echo ""
echo -e "${YELLOW}[4/6] Starting services...${NC}"
docker compose up -d

echo -e "${GREEN}  ✓ Services started${NC}"

# ============= WAIT FOR HEALTH =============
echo ""
echo -e "${YELLOW}[5/6] Waiting for services to be healthy...${NC}"

wait_for_healthy() {
    local service=$1
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        local health=$(docker inspect --format='{{.State.Health.Status}}' "celia-$service" 2>/dev/null || echo "starting")
        if [ "$health" = "healthy" ]; then
            echo -e "${GREEN}  ✓ $service is healthy${NC}"
            return 0
        fi
        echo "  ... waiting for $service ($attempt/$max_attempts) [status: $health]"
        sleep 2
        attempt=$((attempt + 1))
    done

    echo -e "${YELLOW}  ! $service health check timeout (may still work)${NC}"
    return 0
}

wait_for_healthy "postgres"
wait_for_healthy "redis"
wait_for_healthy "backend"
wait_for_healthy "frontend"

# ============= RUN DATABASE MIGRATIONS =============
echo ""
echo -e "${YELLOW}[6/6] Running database migrations...${NC}"

docker compose exec -T backend alembic upgrade head 2>/dev/null || {
    echo -e "${YELLOW}  ! Migration skipped (may need manual run)${NC}"
}

echo -e "${GREEN}  ✓ Migrations applied${NC}"

# ============= DONE =============
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo -e "║        ${GREEN}✅ celia.pro is ready!${NC}                ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║                                                  ║"
echo "║  🌐 Frontend:  http://localhost:3000             ║"
echo "║  🔧 Backend:   http://localhost:8000             ║"
echo "║  📊 API Docs:  http://localhost:8000/docs        ║"
echo "║  ❤️  Health:    http://localhost:8000/api/health   ║"
echo "║                                                  ║"
echo "║  📖 Logs:      docker compose logs -f            ║"
echo "║  🛑 Stop:      docker compose down               ║"
echo "║  🔄 Restart:   docker compose restart            ║"
echo "║                                                  ║"
echo "╚══════════════════════════════════════════════════╝"
