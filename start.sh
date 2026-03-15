#!/usr/bin/env bash
set -euo pipefail
# Start Gasket Gateway — production mode (3 HA instances)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Building gasket:dev image..."
docker compose build

echo "Starting Gasket Gateway (production — 3 instances)..."
docker compose up -d

echo ""
echo "Gasket Gateway is running:"
echo "  Instance 1:  http://localhost:5000  (metrics: http://localhost:9050)"
echo "  Instance 2:  http://localhost:5001  (metrics: http://localhost:9051)"
echo "  Instance 3:  http://localhost:5002  (metrics: http://localhost:9052)"
echo "  PostgreSQL:  localhost:5432"
