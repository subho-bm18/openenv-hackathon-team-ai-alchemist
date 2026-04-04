#!/usr/bin/env bash
set -uo pipefail

DOCKER_BUILD_TIMEOUT=600
PING_URL="${1:-}"
REPO_DIR="${2:-.}"

if [ -z "$PING_URL" ]; then
  printf "Usage: %s <ping_url> [repo_dir]\n" "$0"
  exit 1
fi

PING_URL="${PING_URL%/}"

echo "Checking HF Space reset endpoint..."
HTTP_CODE=$(curl -s -o /tmp/openenv-validate.out -w "%{http_code}" -X POST -H "Content-Type: application/json" -d '{}' "$PING_URL/reset" --max-time 30 || printf "000")
if [ "$HTTP_CODE" != "200" ]; then
  echo "HF Space reset endpoint failed with status $HTTP_CODE"
  exit 1
fi

echo "Building Docker image..."
docker build "$REPO_DIR"

echo "Running openenv validate..."
(cd "$REPO_DIR" && openenv validate)

echo "Submission validation checks passed."
