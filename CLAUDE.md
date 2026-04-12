# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Todo app: Vue 3 (Quasar v2) frontend + AWS SAM (Lambda Python 3.12 + DynamoDB + API Gateway HTTP API v2) backend. TDD (t-wada style Red→Green→Refactor) で開発。

## Commands

### Backend (from `backend/`)

```bash
# Setup
uv venv && source .venv/bin/activate
uv pip install -r requirements-dev.txt

# Test (AWS_DEFAULT_REGION required for moto)
AWS_DEFAULT_REGION=ap-northeast-1 .venv/bin/python -m pytest tests/ -v
AWS_DEFAULT_REGION=ap-northeast-1 .venv/bin/python -m pytest tests/unit/shared/test_models.py -v  # single file
AWS_DEFAULT_REGION=ap-northeast-1 .venv/bin/python -m pytest tests/unit/handlers/ -v              # directory

# Lint & Format
.venv/bin/ruff check src/ tests/
.venv/bin/ruff format src/ tests/

# Local API (DynamoDB Local + SAM)
make dev-backend    # docker compose up + create-table + sam build + sam local start-api
```

### Frontend (from `frontend/`)

```bash
npm install
npm run test                  # vitest run
npm run test:watch            # vitest watch
npx vitest run tests/unit/services/todo.service.test.ts  # single file
npm run lint                  # eslint
npm run format:check          # prettier --check
npm run format                # prettier --write
npm run dev                   # quasar dev → http://localhost:9000
npm run build                 # quasar build → dist/spa/
```

## Architecture

### Backend

Lambda handlers (1 function = 1 endpoint) in `backend/src/handlers/` share utilities from `backend/src/shared/`:
- `dynamo_helper.py` — DynamoDB Table resource singleton (reads `TABLE_NAME` env var)
- `response_builder.py` — `success(body, status)` / `error(msg, status)` with Decimal JSON encoding
- `models.py` — `create_todo_item(title)` generates UUID, PK=`TODO#<uuid>`, timestamps

DynamoDB key design: single-table, PK=`TODO#<uuid>` (String), no GSI. Uses Scan (MVP).

SAM template (`template.yaml`) defines HttpApi v2 with CORS for localhost:9000 and *.amplifyapp.com.

### Frontend

Component tree: `TodoPage.vue` → `TodoForm.vue` + `TodoList.vue` → `TodoItem.vue`

Data flow: `useTodos()` composable holds reactive state (`todos`, `loading`, `error`) and calls `todoService` (thin wrapper over axios with `VITE_API_URL` base). Path alias `src/*` → `./src/*`.

### Testing

- Backend: pytest + moto (mock AWS). Shared `dynamo_table` fixture in `tests/conftest.py` creates mock DynamoDB table. Each handler test uses `@mock_aws` decorator.
- Frontend: Vitest + happy-dom + @vue/test-utils. Services tested via `vi.mock('src/services/api')`. Composables tested via `vi.mock('src/services/todo.service')`.

### Local Dev

DynamoDB Local (Docker) で完全ローカル動作。`make dev-backend` で DynamoDB Local 起動 + テーブル作成 + SAM API 起動を一括実行。`env.json` で `DYNAMODB_ENDPOINT=http://host.docker.internal:8000` を Lambda コンテナに渡す。

### CI/CD

- GitHub Actions + OIDC 認証 (長期 Access Key 不使用)
- `backend.yml`: lint → test → (main push のみ) sam deploy
- `frontend.yml`: lint → test (デプロイは Amplify 側で自動)
- AWS 側セットアップ: `infra/github-oidc.yaml` で OIDC プロバイダー + IAM ロール作成
- GitHub Secrets: `AWS_ROLE_ARN` のみ
