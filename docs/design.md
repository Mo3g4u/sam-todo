# SAM Todo App 設計ドキュメント

## 概要

Todo アプリを以下の構成で構築する。

| レイヤー | 技術スタック |
|---|---|
| フロントエンド | Vue 3 + Quasar v2 (TypeScript, Composition API) |
| ホスティング | AWS Amplify Gen2 (amplify.yml CI/CD) |
| API | Amazon API Gateway (HTTP API v2) |
| コンピュート | AWS Lambda (Python 3.12, arm64) |
| データベース | Amazon DynamoDB (オンデマンド) |
| IaC | AWS SAM |

- 認証: なし (MVP)
- 環境: dev のみ
- ローカル開発: DynamoDB Local (Docker) + `sam local start-api` + Quasar dev server
- 開発手法: t-wada 流 TDD (テスト駆動開発)
  - Red → Green → Refactor サイクルを厳守
  - テストファーストで実装を進める
  - バックエンド (pytest) / フロントエンド (Vitest) それぞれでテストを先に書く
- コード品質ツール:
  - バックエンド: Ruff (linter + formatter)
  - フロントエンド: ESLint (linter) + Prettier (formatter)

---

## 1. プロジェクト構成

```
sam-todo/
├── docs/
│   ├── design.md                   # 本ドキュメント
│   └── architecture.md             # アーキテクチャ詳細 (図付き)
├── backend/
│   ├── template.yaml               # SAM テンプレート (ローカル開発用)
│   ├── template-deploy.yaml        # SAM テンプレート (AWS デプロイ用)
│   ├── docker-compose.yml          # DynamoDB Local
│   ├── env.json                    # ローカル用環境変数
│   ├── scripts/create-table.sh     # テーブル自動作成
│   ├── pyproject.toml              # pytest + Ruff 設定
│   ├── requirements-dev.txt        # 開発依存 (pytest, moto, ruff)
│   └── src/
│       ├── requirements.txt        # Lambda 依存 (boto3)
│       ├── handlers/
│       │   ├── __init__.py
│       │   ├── create_todo.py      # POST /todos
│       │   ├── list_todos.py       # GET /todos
│       │   ├── get_todo.py         # GET /todos/{id}
│       │   ├── update_todo.py      # PUT /todos/{id}
│       │   └── delete_todo.py      # DELETE /todos/{id}
│       └── shared/
│           ├── __init__.py
│           ├── dynamo_helper.py    # DynamoDB テーブル取得
│           ├── response_builder.py # HTTP レスポンス + CORS ビルダー
│           └── models.py           # Todo データモデル
├── frontend/
│   ├── package.json
│   ├── quasar.config.ts
│   ├── vitest.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── .eslintrc.cjs / .prettierrc
│   ├── .npmrc                      # ignore-scripts=true
│   ├── .env.development            # VITE_API_URL=http://localhost:3000
│   └── src/
│       ├── App.vue
│       ├── router/
│       │   ├── index.ts
│       │   └── routes.ts
│       ├── pages/
│       │   └── TodoPage.vue
│       ├── components/
│       │   ├── TodoList.vue
│       │   ├── TodoItem.vue
│       │   └── TodoForm.vue
│       ├── composables/
│       │   └── useTodos.ts
│       ├── services/
│       │   ├── api.ts
│       │   └── todo.service.ts
│       └── types/
│           └── todo.ts
├── e2e/
│   └── todo_app.py                 # Playwright E2E テスト
├── infra/
│   └── github-oidc.yaml           # OIDC 用 CloudFormation
├── .github/
│   ├── workflows/
│   │   ├── backend.yml            # Backend CI/CD
│   │   ├── frontend.yml           # Frontend CI
│   │   └── dependency-review.yml  # PR 依存チェック
│   └── dependabot.yml             # 自動依存更新
├── amplify.yml
├── Makefile
├── CLAUDE.md
└── README.md
```

---

## 2. バックエンド設計

### 2.1 SAM テンプレート方針

2 つのテンプレートを使い分ける:

| テンプレート | 用途 | ルーティング方式 |
|---|---|---|
| `template.yaml` | ローカル開発 (`sam local start-api`) | SAM Events (自動ルーティング) |
| `template-deploy.yaml` | AWS デプロイ (GitHub Actions) | OpenAPI DefinitionBody + IAM ロール + Cognito + JWT Authorizer |

**DefinitionBody を使う理由**: AWS Control Tower の SCP (`CT.LAMBDA.PV.2`) が `lambda:AddPermission` をブロックするため、SAM Events の自動生成する `AWS::Lambda::Permission` が使えない。代わりに API Gateway が IAM ロール (`ApiGatewayInvokeRole`) を AssumeRole して Lambda を呼び出す。詳細は [Control Tower 対応の解説](control-tower-lambda-permission.md) を参照。

共通設定:
- **API Gateway**: `AWS::Serverless::HttpApi` (v2)。REST API (v1) より低コスト・低レイテンシー
- **Globals**: Python 3.12, arm64 (Graviton2), timeout 10s, memory 128MB
- **IAM**: `DynamoDBCrudPolicy` SAM ポリシーテンプレートで最小権限
- **構成**: 1 ハンドラー = 1 Lambda 関数。`CodeUri: src/` で shared も含まれる

### 2.2 DynamoDB テーブル設計

```
テーブル名: todo-table-v2
BillingMode: PAY_PER_REQUEST (オンデマンド)

PK (Partition Key): "USER#<userId>" (String) ← Cognito sub
SK (Sort Key):      "TODO#<uuid>" (String)

属性:
  PK:         "USER#a1b2c3..."
  SK:         "TODO#f1e2d3..."
  id:         "f1e2d3..."                # API レスポンス用
  title:      "買い物に行く"
  completed:  false
  created_at: "2026-04-10T12:00:00Z"     # ISO 8601
  updated_at: "2026-04-10T12:00:00Z"
```

- **GSI**: なし。`query(PK=USER#xxx)` でユーザーの Todo のみ効率的に取得
- **ユーザー分離**: PK にユーザー ID を含めることで、他ユーザーのデータにはアクセス不可

### 2.3 CORS 設定

Lambda レスポンスに CORS ヘッダーを直接含める方式。`response_builder.py` が全レスポンスに以下を付与:

- `Access-Control-Allow-Origin`: `ALLOWED_ORIGINS` 環境変数 (デフォルト: `http://localhost:9000`)
- `Access-Control-Allow-Methods`: `GET,POST,PUT,DELETE,OPTIONS`
- `Access-Control-Allow-Headers`: `Content-Type`

OPTIONS プリフライトは `template-deploy.yaml` の `x-amazon-apigateway-cors` で API Gateway が自動処理。

### 2.4 共通ユーティリティ (shared/)

| ファイル | 役割 | 主要関数 |
|---|---|---|
| `auth.py` | JWT claims からユーザー ID を取得 | `get_user_id(event)` |
| `dynamo_helper.py` | DynamoDB テーブルのシングルトン取得。`DYNAMODB_ENDPOINT` でローカル接続切替 | `get_table()` |
| `response_builder.py` | HTTP レスポンス + CORS ヘッダー。Decimal 対応 JSON シリアライズ | `success(body, status)`, `error(msg, status)` |
| `models.py` | Todo データモデル。UUID 生成、タイムスタンプ、PK/SK 生成 | `create_todo_item(user_id, title)` |

### 2.5 Lambda ハンドラー

全ハンドラーに try/except を設置。DynamoDB エラーは 500 で返す。

| エンドポイント | ハンドラー | レスポンス | 主要ロジック |
|---|---|---|---|
| `POST /todos` | `create_todo.handler` | 201 | body から title 取得 → models で item 生成 → put_item |
| `GET /todos` | `list_todos.handler` | 200 | scan → created_at 降順ソート |
| `GET /todos/{id}` | `get_todo.handler` | 200 / 404 | PK=TODO#{id} で get_item |
| `PUT /todos/{id}` | `update_todo.handler` | 200 / 404 | 動的 UpdateExpression 構築 → update_item |
| `DELETE /todos/{id}` | `delete_todo.handler` | 204 | PK=TODO#{id} で delete_item |

---

## 3. フロントエンド設計

### 3.1 セットアップ

- Quasar v2 + Vite + TypeScript + Composition API
- Node.js 24+ (LTS)
- `@quasar/app-vite` ^2.6.0
- `amazon-cognito-identity-js` (認証)
- `axios` 1.15.0 (サプライチェーン攻撃後の安全なバージョンに固定)

### 3.2 型定義

```typescript
// types/todo.ts
export interface Todo {
  id: string;
  title: string;
  completed: boolean;
  created_at: string;
  updated_at?: string;
}

export interface CreateTodoRequest {
  title: string;
}

export interface UpdateTodoRequest {
  title?: string;
  completed?: boolean;
}
```

### 3.3 API 通信レイヤー

```
services/api.ts            → axios インスタンス (baseURL: VITE_API_URL) + JWT インターセプター
services/auth.service.ts   → signUp(), confirmSignUp(), signIn(), signOut(), getIdToken()
services/todo.service.ts   → list(), get(id), create(data), update(id, data), remove(id)
composables/useAuth.ts     → 認証状態管理 (email, isAuthenticated, loading, error)
```

### 3.4 コンポーネント構成

```
App.vue                        ← q-layout + q-header (メール表示 + ログアウト)
└── router-view
    ├── LoginPage.vue          ← メール + パスワード → signIn
    ├── SignupPage.vue         ← サインアップ + 確認コード入力
    └── TodoPage.vue           ← useTodos() (認証必須, auth-guard で保護)
        ├── TodoForm.vue       q-input (title) + q-btn (追加)
        └── TodoList.vue       q-list + q-spinner (loading) + 空状態メッセージ
             └── TodoItem.vue  q-item + q-checkbox (完了トグル) + q-btn (削除)
```

### 3.5 Composable (useTodos.ts)

| 状態 | 型 | 用途 |
|---|---|---|
| `todos` | `Ref<Todo[]>` | Todo 一覧 |
| `loading` | `Ref<boolean>` | ローディング状態 |
| `error` | `Ref<string \| null>` | エラーメッセージ |

| 関数 | 説明 |
|---|---|
| `fetchTodos()` | 一覧取得 |
| `addTodo(title)` | 新規作成 |
| `toggleTodo(todo)` | 完了状態トグル |
| `removeTodo(id)` | 削除 |

### 3.6 環境変数

| ファイル | 変数 | 値 |
|---|---|---|
| `.env.development` | `VITE_API_URL` | `http://localhost:3000` |
| `.env.development` | `VITE_COGNITO_USER_POOL_ID` | (ローカルでは空 = 認証なし) |
| `.env.development` | `VITE_COGNITO_CLIENT_ID` | (ローカルでは空 = 認証なし) |
| `.env.production` | (上記 3 変数) | Amplify ビルド時に `amplify.yml` で注入 |

---

## 4. Amplify Gen2 ホスティング

### 4.1 amplify.yml (リポジトリルート)

```yaml
version: 1
frontend:
  phases:
    preBuild:
      commands:
        - nvm install 24
        - nvm use 24
        - cd frontend
        - npm ci --cache .npm --prefer-offline
    build:
      commands:
        - echo "VITE_API_URL=$VITE_API_URL" > .env.production
        - echo "VITE_COGNITO_USER_POOL_ID=$VITE_COGNITO_USER_POOL_ID" >> .env.production
        - echo "VITE_COGNITO_CLIENT_ID=$VITE_COGNITO_CLIENT_ID" >> .env.production
        - npm run build
  artifacts:
    baseDirectory: frontend/dist/spa
    files:
      - "**/*"
  cache:
    paths:
      - frontend/.npm/**/*
      - frontend/node_modules/**/*
```

### 4.2 設定ポイント

- Quasar SPA のビルド出力は `dist/spa/`
- Amplify のデフォルト Node が古いため `nvm install 24` で Node 24 LTS を使用
- preBuild で `cd frontend` した後、build フェーズは同じディレクトリを引き継ぐ
- Amplify コンソールで環境変数 `VITE_API_URL`, `VITE_COGNITO_USER_POOL_ID`, `VITE_COGNITO_CLIENT_ID` を設定
- SPA リダイレクトルール: `/<*>` → `/index.html` (200 Rewrite) を Amplify コンソールで設定

---

## 5. ローカル開発フロー

### 前提条件

- Docker Desktop
- Python 3.12 + uv
- Node.js 24+
- SAM CLI

### 起動手順

```bash
# セットアップ (初回のみ)
make setup

# ターミナル 1: バックエンド (DynamoDB Local + SAM API)
make dev-backend
# → DynamoDB Local (Docker) 起動 → テーブル作成 → sam build → http://localhost:3000

# ターミナル 2: フロントエンド
make dev-frontend
# → http://localhost:9000
```

### 構成

```
Quasar Dev (9000) → SAM Local API (3000) → DynamoDB Local (8000)
```

- `backend/env.json` で `DYNAMODB_ENDPOINT=http://host.docker.internal:8000` を Lambda コンテナに渡す
- `dynamo_helper.py` が `DYNAMODB_ENDPOINT` を検出するとローカル接続 (ダミー認証) に切り替え
- DynamoDB Local は in-memory モードのため、再起動でデータが消える

---

## 6. CI/CD

### 6.1 GitHub Actions (OIDC 認証)

- GitHub → AWS 間の認証は OIDC (OpenID Connect) を使用。長期 Access Key は使わない
- AWS 側セットアップ: `infra/github-oidc.yaml` を手動デプロイして OIDC プロバイダー + IAM ロールを作成
- GitHub Secrets: `AWS_ROLE_ARN` + `FRONTEND_URL` (Amplify URL)
- Amplify 環境変数: `VITE_API_URL` + `VITE_COGNITO_USER_POOL_ID` + `VITE_COGNITO_CLIENT_ID`

### 6.2 ワークフロー

| ワークフロー | トリガー | 処理 |
|---|---|---|
| `backend.yml` | `backend/**` への push/PR, 手動 | lint → test → (main のみ) sam deploy |
| `frontend.yml` | `frontend/**` への push/PR | lint → test → npm audit → audit signatures |
| `dependency-review.yml` | 全 PR | 脆弱性 (high+) + ライセンス (GPL/AGPL) 検査 |

### 6.3 デプロイフロー

```
1. main に push → backend.yml が sam build (template-deploy.yaml) && sam deploy (OIDC 認証)
2. Amplify コンソールで VITE_API_URL 環境変数に API URL を設定 (初回 or URL 変更時のみ)
3. main に push → Amplify 自動ビルド・デプロイ (フロントエンド)
```

### 6.4 Control Tower 対応

AWS Control Tower の SCP (`CT.LAMBDA.PV.2`) が `lambda:AddPermission` をブロックするため、SAM のデフォルト動作 (Events → Lambda::Permission 自動生成) ではデプロイに失敗する。

**対策**: AssumeRole 方式
- `template-deploy.yaml` で OpenAPI DefinitionBody を使用
- `ApiGatewayInvokeRole` IAM ロールで API Gateway が Lambda を呼び出す
- `lambda:AddPermission` を完全に回避

### 6.5 初回セットアップ手順

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

### 6.6 サプライチェーン防御策

| # | 防御策 | 設定内容 | 対象ファイル |
|---|---|---|---|
| 1 | Dependabot Alerts | GitHub Settings → Code security で有効化 | (リポジトリ設定) |
| 2 | dependabot.yml | npm / pip / github-actions の週次自動更新 | `.github/dependabot.yml` |
| 3 | Dependency Review | PR 時に high 以上の脆弱性 + GPL/AGPL を拒否 | `.github/workflows/dependency-review.yml` |
| 4 | npm audit in CI | `npm audit --audit-level=high` でビルド時に脆弱性検出 | `.github/workflows/frontend.yml` |
| 5 | npm audit signatures | `npm audit signatures` でパッケージ真正性検証 | `.github/workflows/frontend.yml` |
| 6 | package-lock.json 厳密管理 | `npm ci` 使用、lock ファイルは git 管理 | `frontend/package-lock.json` |
| 7 | ignore-scripts | `postinstall` 等の悪意あるスクリプト実行を防止 | `frontend/.npmrc` |
| 8 | Actions SHA ピン留め | 全 Actions をフルレングス SHA で固定 | `.github/workflows/*.yml` |

---

## 7. テスト戦略

### バックエンド (pytest + moto)

| テスト | 件数 | 内容 |
|---|---|---|
| handlers | 15 | CRUD 正常系・異常系 + 他ユーザーデータアクセス不可 |
| shared | 18 | auth, models, response_builder, dynamo_helper |
| **合計** | **33** | |

### フロントエンド (Vitest + happy-dom)

| テスト | 件数 | 内容 |
|---|---|---|
| services | 5 | todoService の API 呼び出し |
| composables | 5 | useTodos の状態管理 |
| **合計** | **10** | |

### E2E (Playwright)

- `e2e/todo_app.py` でブラウザ自動テスト
- 空リスト表示 / Todo 追加 / 2件追加 / 完了トグル / 削除

---

## 8. 検証方法

### バックエンド (curl)

```bash
# 作成
curl -s -X POST http://localhost:3000/todos \
  -H "Content-Type: application/json" \
  -d '{"title":"テストTodo"}' | jq

# 一覧
curl -s http://localhost:3000/todos | jq

# 更新
curl -s -X PUT http://localhost:3000/todos/{id} \
  -H "Content-Type: application/json" \
  -d '{"completed":true}' | jq

# 削除
curl -s -X DELETE http://localhost:3000/todos/{id}
```

### フロントエンド

- `make dev-frontend` でブラウザ確認
- Todo の追加・一覧表示・完了トグル・削除が動作すること

### デプロイ後

- Amplify URL にアクセス → API 経由で CRUD 操作が動作すること
