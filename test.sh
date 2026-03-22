#!/usr/bin/env bash
set -euo pipefail
# Build, start the test environment, run general tests, then stop.
# Results are written to test-results/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

COMPOSE="docker compose -f docker-compose-dev.yaml -f docker-compose-test.yaml"

echo "═══════════════════════════════════════════════"
echo "  Gasket Gateway — General Tests"
echo "═══════════════════════════════════════════════"
echo ""

echo "Clearing previous results and logs..."
rm -f test-results/*.xml test-results/*.html test-results/*.png
rm -f logs/*.log
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
echo "Running tests..."
$COMPOSE run --rm test-runner \
    python -m pytest tests/ --ignore=tests/oidc/ \
    -v --tb=short \
    --junitxml=/results/general-results.xml \
    --html=/results/general-report.html --self-contained-html \
    "$@"
EXIT_CODE=$?

echo ""
echo "Results written to test-results/"
echo "Stopping test environment..."
$COMPOSE down

exit $EXIT_CODE
