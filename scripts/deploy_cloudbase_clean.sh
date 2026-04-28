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
  --exclude 'data/*.db' \
  --exclude 'backups/' \
  --exclude 'scratch/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.pytest_cache/'

# 使用 tcb framework deploy 以应用 cloudbaserc.json 中的实例数配置 (minCount=1, maxCount=1)
cd "$DEPLOY_DIR"
/Users/fuhongbo/.npm-global/bin/tcb framework deploy \
  -e "$ENV_ID" \
  --force
