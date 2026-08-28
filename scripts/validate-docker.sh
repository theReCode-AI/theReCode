#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Validating docker compose configuration..."
docker compose config > /dev/null

echo "Building application images..."
docker compose --profile app build

echo "Starting MongoDB..."
docker compose up -d mongodb

echo "Waiting for MongoDB..."
for _ in $(seq 1 30); do
  if docker compose exec -T mongodb mongosh --eval "db.adminCommand('ping')" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! docker compose exec -T mongodb mongosh --eval "db.adminCommand('ping')" >/dev/null 2>&1; then
  echo "MongoDB failed to become healthy" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.docker.example .env
fi

echo "Starting backend and frontend..."
docker compose --profile app up -d backend frontend

echo "Waiting for backend readiness..."
for _ in $(seq 1 40); do
  if curl -fsS http://127.0.0.1:8000/api/v1/health/ready >/dev/null 2>&1; then
    break
  fi
  sleep 3
done

curl -fsS http://127.0.0.1:8000/api/v1/health/ready
echo
curl -fsS http://127.0.0.1:5173/ >/dev/null
curl -fsS http://127.0.0.1:5173/api/v1/health
echo

echo "Docker stack validation succeeded."
