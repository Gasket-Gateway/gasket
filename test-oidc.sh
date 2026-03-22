#!/usr/bin/env bash
set -euo pipefail
# Build, start Gasket (without test mode), run OIDC tests, then stop.
# Prerequisites: Full dev environment (Authentik, Traefik, etc.) already running.
# Results + failure screenshots are written to test-results/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

COMPOSE="docker compose -f docker-compose-dev.yaml -f docker-compose-test-runner.yaml"

echo "═══════════════════════════════════════════════"
echo "  Gasket Gateway — OIDC Flow Tests"
echo "═══════════════════════════════════════════════"
echo ""

echo "Clearing previous results and logs..."
rm -f test-results/*.xml test-results/*.html test-results/*.png
rm -f logs/*.log
echo ""

echo "Building images..."
$COMPOSE build

echo "Starting Gasket (OIDC enabled)..."
$COMPOSE up -d gasket

echo "Waiting for Gasket to be ready..."
until curl -skf https://portal.gasket-dev.local/health > /dev/null 2>&1; do
    echo -n "."
    sleep 2
done
echo " ready"

echo ""
echo "Running OIDC tests..."
$COMPOSE run --rm test-runner \
    python -m pytest tests/oidc/ \
    -v --tb=short \
    --junitxml=/results/oidc-results.xml \
    --html=/results/oidc-report.html --self-contained-html \
    "$@"
EXIT_CODE=$?

echo ""
echo "Results written to test-results/"
echo "  Screenshots of failures: test-results/*.png"
echo "Stopping Gasket..."
$COMPOSE down

exit $EXIT_CODE
