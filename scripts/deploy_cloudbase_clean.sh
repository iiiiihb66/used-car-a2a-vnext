#!/usr/bin/env bash
set -euo pipefail

ENV_ID="${TCB_ENV_ID:-car-assistant-prod-3dqle77ef680c}"
SERVICE_NAME="${TCB_SERVICE_NAME:-used-car-a2a-vnext}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$(mktemp -d /tmp/used-car-a2a-deploy.XXXXXX)"

cleanup() {
  rm -rf "$DEPLOY_DIR"
}
trap cleanup EXIT

rsync -a "$PROJECT_ROOT/" "$DEPLOY_DIR/" \
  --exclude '.git/' \
  --exclude '.secrets/' \
  --exclude '.env' \
  --exclude '.env.*' \
  --exclude 'cloudbaserc.json' \
  --exclude 'data/*.db' \
  --exclude 'backups/' \
  --exclude 'scratch/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.pytest_cache/'

/Users/fuhongbo/.npm-global/bin/tcb cloudrun deploy \
  -e "$ENV_ID" \
  -s "$SERVICE_NAME" \
  --source "$DEPLOY_DIR" \
  --port 80 \
  --force
