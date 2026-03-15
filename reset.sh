#!/usr/bin/env bash
set -euo pipefail
# Reset Gasket Gateway — removes containers AND volumes (works for both prod and dev)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

docker compose down -v 2>/dev/null || true
docker compose -f docker-compose-dev.yaml down -v 2>/dev/null || true

echo "Gasket Gateway reset (containers and volumes removed)."
