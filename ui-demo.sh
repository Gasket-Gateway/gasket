#!/usr/bin/env bash
set -euo pipefail
# Start Gasket Gateway with test mode enabled (UI Demo & injected admin user)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Stop any running instances first
./stop.sh

echo "Building gasket:dev image..."
docker compose -f docker-compose-dev.yaml -f docker-compose-test.yaml build gasket

echo "Starting Gasket Gateway (UI Demo mode)..."
docker compose -f docker-compose-dev.yaml -f docker-compose-test.yaml up -d gasket

echo ""
echo "Gasket Gateway is running with Test Mode enabled (Admin User Injected):"
echo "  Portal:      http://localhost:5000"
echo "  UI Demo:     http://localhost:5000/ui-demo"
echo "  Admin Panel: http://localhost:5000/admin/"
echo "  Health:      http://localhost:5000/health"
echo "  Metrics:     http://localhost:9050/metrics"
echo "  PostgreSQL:  localhost:5432"
echo ""
echo "To stop, run: ./stop.sh"
