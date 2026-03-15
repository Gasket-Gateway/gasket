#!/usr/bin/env bash
set -euo pipefail
# Start Gasket Gateway — development mode (single instance, Flask dev server)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Building gasket:dev image..."
docker compose -f docker-compose-dev.yaml build

echo "Starting Gasket Gateway (dev — single instance)..."
docker compose -f docker-compose-dev.yaml up -d

echo ""
echo "Gasket Gateway is running (dev mode):"
echo "  Portal:      http://localhost:5000"
echo "  UI Demo:     http://localhost:5000/ui-demo"
echo "  Health:      http://localhost:5000/health"
echo "  Metrics:     http://localhost:9050/metrics"
echo "  PostgreSQL:  localhost:5432"
