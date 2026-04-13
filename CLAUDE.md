# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Todo app: Vue 3 (Quasar v2) frontend + AWS SAM (Lambda Python 3.12 + DynamoDB + API Gateway HTTP API v2) backend. Amazon Cognito によるメール + パスワード認証付き。TDD (t-wada style Red→Green→Refactor) で開発。

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
- `auth.py` — `get_user_id(event)` で JWT claims から Cognito userId (sub) を取得
- `dynamo_helper.py` — DynamoDB Table resource singleton (`DYNAMODB_ENDPOINT` でローカル接続切り替え)
- `response_builder.py` — `success(body, status)` / `error(msg, status)` with Decimal JSON encoding + CORS ヘッダー (`ALLOWED_ORIGINS` env var)
- `models.py` — `create_todo_item(user_id, title)` generates PK=`USER#<userId>`, SK=`TODO#<uuid>`

DynamoDB key design: PK=`USER#<userId>` (Cognito sub), SK=`TODO#<uuid>`. `list_todos` は `query(PK=USER#xxx)` でユーザーのデータのみ取得。

Two SAM templates:
- `template.yaml` — ローカル開発用 (Events ベース、`sam local start-api` 互換)
- `template-deploy.yaml` — AWS デプロイ用 (DefinitionBody + IAM ロール + Cognito + JWT Authorizer)

### Frontend

Component tree: `App.vue` (ヘッダー + ログアウト) → `LoginPage` / `SignupPage` / `TodoPage` → `TodoForm` + `TodoList` → `TodoItem`

認証: `auth.service.ts` (Cognito SDK) → `useAuth()` composable → auth-guard (router beforeEach)
データ: `useTodos()` composable → `todoService` → `api.ts` (axios + JWT インターセプター)

### Testing

- Backend: pytest + moto (mock AWS). 33 テスト。`conftest.py` の `make_event()` で JWT claims 付きイベント生成。他ユーザーデータへのアクセス不可を検証。
- Frontend: Vitest + happy-dom + @vue/test-utils. 10 テスト。

### Local Dev

DynamoDB Local (Docker) で完全ローカル動作。`make dev-backend` で DynamoDB Local 起動 + テーブル作成 + SAM API 起動を一括実行。`env.json` で `DYNAMODB_ENDPOINT=http://host.docker.internal:8000` を Lambda コンテナに渡す。ローカルでは JWT 認証なしで動作。

### CI/CD

- GitHub Actions + OIDC 認証 (長期 Access Key 不使用)
- `backend.yml`: lint → test → (main push/手動のみ) sam deploy (template-deploy.yaml)
- `frontend.yml`: lint → test → npm audit → audit signatures (デプロイは Amplify 側で自動)
- `dependency-review.yml`: PR 時に脆弱な依存・禁止ライセンスを検出
- AWS 側セットアップ: `infra/github-oidc.yaml` で OIDC プロバイダー + IAM ロール作成
- GitHub Secrets: `AWS_ROLE_ARN`, `FRONTEND_URL`
- Amplify 環境変数: `VITE_API_URL`, `VITE_COGNITO_USER_POOL_ID`, `VITE_COGNITO_CLIENT_ID`

### Supply Chain Security

- axios 1.15.0 に固定 (2026年3月のサプライチェーン攻撃後の安全なバージョン)
- 全 Actions は SHA ピン留め（タグではなくフルレングス SHA で固定）
- Dependabot が npm / pip / github-actions の依存を週次で自動更新
- `frontend/.npmrc` に `ignore-scripts=true` で postinstall 攻撃を防止
- PR 時に Dependency Review Action で脆弱性 + ライセンス検査
