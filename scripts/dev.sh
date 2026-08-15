#!/bin/bash
# celia.pro - Start development environment
# Usage: ./scripts/dev.sh
set -euo pipefail

echo "╔══════════════════════════════════════════════════╗"
echo "║        🛠️  celia.pro Development Mode            ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Start development services
echo -e "${YELLOW}Starting development services...${NC}"
docker compose -f docker-compose.dev.yml up --build

# Cleanup on exit
trap "echo -e '\n${YELLOW}Stopping development services...${NC}' && docker compose -f docker-compose.dev.yml down" EXIT
