# SAM Todo App

Vue 3 (Quasar) + AWS SAM (Lambda + DynamoDB + API Gateway) で構成した Todo アプリ。

## 技術スタック

| レイヤー | 技術 |
|---|---|
| フロントエンド | Vue 3 + Quasar v2 (TypeScript, Composition API) |
| ホスティング | AWS Amplify Gen2 |
| API | Amazon API Gateway (HTTP API v2) |
| コンピュート | AWS Lambda (Python 3.12, arm64) |
| データベース | Amazon DynamoDB (オンデマンド) |
| IaC | AWS SAM |

## ローカル開発

### 前提条件

- Docker Desktop
- AWS CLI (`aws configure` 設定済み)
- Python 3.12 + uv
- Node.js 18+
- SAM CLI

### バックエンド

```bash
cd backend
uv venv && source .venv/bin/activate
uv pip install -r requirements-dev.txt

# テスト
AWS_DEFAULT_REGION=ap-northeast-1 python -m pytest tests/ -v

# lint / format
ruff check src/ tests/
ruff format src/ tests/

# ローカル起動
sam build
sam local start-api --port 3000 --warm-containers EAGER
```

### フロントエンド

```bash
cd frontend
npm install

# テスト
npx vitest run

# lint / format
npm run lint
npm run format:check

# ローカル起動
npx quasar dev
# → http://localhost:9000
```

## デプロイ

```bash
# 1. バックエンド
cd backend
sam build && sam deploy --guided

# 2. Amplify コンソールで VITE_API_URL を設定

# 3. git push → Amplify 自動デプロイ
```
