#!/usr/bin/env bash
set -euo pipefail
# Build, start the test environment, run the demo screenshot suite, then stop.
# Screenshots are written to test-results/screenshots/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

COMPOSE="docker compose -f docker-compose-dev.yaml -f docker-compose-test.yaml"

echo "═══════════════════════════════════════════════"
echo "  Gasket Gateway — Screenshot Demo Capture"
echo "═══════════════════════════════════════════════"
echo ""

echo "Clearing previous screenshots and logs..."
rm -rf test-results/screenshots/*
rm -f logs/*.log
mkdir -p test-results/screenshots
echo ""

echo "Building images..."
$COMPOSE build

echo "Starting test environment..."
$COMPOSE up -d gasket

echo "Waiting for Gasket to be ready..."
until curl -sf http://localhost:5000/health > /dev/null 2>&1; do
    echo -n "."
    sleep 2
done
echo " ready"

echo ""
echo "Running demo screenshots suite..."
$COMPOSE run --rm test-runner \
    python -m pytest tests/demo/ \
    -v --tb=short \
    "$@"
EXIT_CODE=$?

echo ""
echo "Screenshots written to test-results/screenshots/"
echo "Stopping test environment..."
$COMPOSE down

exit $EXIT_CODE
