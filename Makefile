.PHONY: setup setup-backend setup-frontend dev dev-backend dev-frontend dev-db build test test-backend test-frontend lint lint-backend lint-frontend format

# === Setup ===
setup: setup-backend setup-frontend

setup-backend:
	cd backend && uv venv && . .venv/bin/activate && uv pip install -r requirements-dev.txt

setup-frontend:
	cd frontend && npm install

# === Local Dev ===
dev-db:
	cd backend && docker compose up -d && ./scripts/create-table.sh

dev-backend: dev-db
	-kill $$(lsof -ti:3000) 2>/dev/null || true
	cd backend && sam build && sam local start-api --port 3000 --warm-containers EAGER --env-vars env.json

dev-frontend:
	cd frontend && npx quasar dev

stop-db:
	cd backend && docker compose down

# === Build ===
build:
	cd backend && sam build
	cd frontend && npm run build

# === Test ===
test: test-backend test-frontend

test-backend:
	cd backend && AWS_DEFAULT_REGION=ap-northeast-1 .venv/bin/python -m pytest tests/ -v

test-frontend:
	cd frontend && npm run test

# === Lint & Format ===
lint: lint-backend lint-frontend

lint-backend:
	cd backend && .venv/bin/ruff check src/ tests/

lint-frontend:
	cd frontend && npm run lint && npm run format:check

format:
	cd backend && .venv/bin/ruff format src/ tests/
	cd frontend && npm run format
