#!/usr/bin/env bash
set -euo pipefail
# Stop Gasket Gateway (works for both prod and dev)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Stop whichever compose file is running
docker compose down 2>/dev/null || true
docker compose -f docker-compose-dev.yaml down 2>/dev/null || true

echo "Gasket Gateway stopped."
