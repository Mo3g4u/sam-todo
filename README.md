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
| CI/CD | GitHub Actions (OIDC 認証) |

## 前提条件

- Docker Desktop
- Python 3.12 + uv
- Node.js 24+
- SAM CLI

## ローカル開発

### セットアップ

```bash
make setup
```

### 起動

```bash
# ターミナル 1: バックエンド (DynamoDB Local + SAM API)
make dev-backend

# ターミナル 2: フロントエンド
make dev-frontend
# → http://localhost:9000
```

### テスト

```bash
make test           # backend + frontend
make test-backend   # pytest のみ
make test-frontend  # vitest のみ
```

### lint / format

```bash
make lint           # ruff check + eslint + prettier check
make format         # ruff format + prettier write
```

## CI/CD

### GitHub Actions

| ワークフロー | トリガー | 処理 |
|---|---|---|
| `backend.yml` | `backend/**` の push/PR | lint → test → (main のみ) sam deploy |
| `frontend.yml` | `frontend/**` の push/PR | lint → test → npm audit |
| `dependency-review.yml` | 全 PR | 脆弱性 + ライセンス検査 |

### 初回セットアップ

```bash
# 1. OIDC プロバイダー + IAM ロールを作成
aws cloudformation deploy \
  --template-file infra/github-oidc.yaml \
  --stack-name github-oidc-sam-todo \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-northeast-1

# 2. ロール ARN を取得
aws cloudformation describe-stacks \
  --stack-name github-oidc-sam-todo \
  --query 'Stacks[0].Outputs[?OutputKey==`RoleArn`].OutputValue' \
  --output text --region ap-northeast-1

# 3. GitHub Secrets に設定
#    AWS_ROLE_ARN: 上記の ARN
#    FRONTEND_URL: Amplify の URL (例: https://main.xxxx.amplifyapp.com)
```

### Amplify ホスティング

1. Amplify コンソール → Git リポジトリ接続 → `main` ブランチ
2. 環境変数 `VITE_API_URL` にバックエンド API URL を設定
3. `git push` → 自動ビルド・デプロイ
