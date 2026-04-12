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
- ローカル開発: `sam local start-api` + Quasar dev server
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
│   └── design.md                  # 本ドキュメント
├── backend/
│   ├── template.yaml              # SAM テンプレート
│   ├── samconfig.toml             # sam deploy 設定 (--guided 後に自動生成)
│   └── src/
│       ├── requirements.txt       # Lambda 用依存
│       ├── handlers/
│       │   ├── __init__.py
│       │   ├── create_todo.py     # POST /todos
│       │   ├── list_todos.py      # GET /todos
│       │   ├── get_todo.py        # GET /todos/{id}
│       │   ├── update_todo.py     # PUT /todos/{id}
│       │   └── delete_todo.py     # DELETE /todos/{id}
│       └── shared/
│           ├── __init__.py
│           ├── dynamo_helper.py   # DynamoDB テーブル取得
│           ├── response_builder.py # HTTP レスポンス統一ビルダー
│           └── models.py          # Todo データモデル・バリデーション
├── frontend/
│   ├── package.json
│   ├── quasar.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── .env.development           # VITE_API_URL=http://localhost:3000/dev
│   ├── .env.production            # VITE_API_URL=<デプロイ後に設定>
│   └── src/
│       ├── App.vue
│       ├── router/
│       │   └── routes.ts
│       ├── pages/
│       │   └── TodoPage.vue       # メインページ
│       ├── components/
│       │   ├── TodoList.vue       # 一覧表示
│       │   ├── TodoItem.vue       # 個別 Todo 表示・操作
│       │   └── TodoForm.vue       # 作成フォーム
│       ├── composables/
│       │   └── useTodos.ts        # CRUD ロジック (Composition API)
│       ├── services/
│       │   ├── api.ts             # axios インスタンス
│       │   └── todo.service.ts    # Todo API 呼び出し
│       └── types/
│           └── todo.ts            # Todo インターフェース
├── amplify.yml                    # Amplify Hosting ビルド設定
├── .gitignore
└── README.md
```

---

## 2. バックエンド設計

### 2.1 SAM template.yaml 方針

- **API Gateway**: `AWS::Serverless::HttpApi` (v2) を使用。REST API (v1) より低コスト・低レイテンシー
- **Globals**: Python 3.12, arm64 (Graviton2), timeout 10s, memory 128MB
- **IAM**: `DynamoDBCrudPolicy` SAM ポリシーテンプレートで最小権限
- **構成**: 1 ハンドラー = 1 Lambda 関数。`CodeUri: src/` で shared も含まれる
- **Lambda Layer**: 使わない (MVP 規模では不要)

### 2.2 DynamoDB テーブル設計

```
テーブル名: todo-table-dev
BillingMode: PAY_PER_REQUEST (オンデマンド)

PK (Partition Key): "TODO#<uuid>" (String)

属性:
  PK:         "TODO#<uuid>"
  id:         "<uuid>"                    # API レスポンス用
  title:      "買い物に行く"
  completed:  false
  created_at: "2026-04-10T12:00:00Z"     # ISO 8601
  updated_at: "2026-04-10T12:00:00Z"
```

- **GSI**: なし。認証なし・小規模のため Scan で十分
- **将来の拡張**: 認証追加時は `PK=USER#<userId>`, `SK=TODO#<uuid>` に移行し、GSI を検討

### 2.3 CORS 設定

- HttpApi の `CorsConfiguration` で以下を許可:
  - `http://localhost:9000` (Quasar dev server)
  - `https://*.amplifyapp.com` (Amplify Hosting)
- HttpApi v2 は OPTIONS プリフライトを自動処理するため、Lambda 側で CORS ヘッダーを返す必要なし
- `sam local start-api` では CORS 自動処理が不完全な場合あり → 環境変数で直接 API URL を指定して対応

### 2.4 共通ユーティリティ (shared/)

| ファイル | 役割 | 主要関数 |
|---|---|---|
| `dynamo_helper.py` | DynamoDB テーブルリソースのシングルトン取得 | `get_table()` |
| `response_builder.py` | HTTP レスポンス統一ビルダー。Decimal 対応 JSON シリアライズ含む | `success(body, status)`, `error(msg, status)` |
| `models.py` | Todo データモデル。UUID 生成、タイムスタンプ、デフォルト値 | `create_todo_item(title)` |

### 2.5 Lambda ハンドラー

| エンドポイント | ハンドラー | レスポンス | 主要ロジック |
|---|---|---|---|
| `POST /todos` | `create_todo.handler` | 201 | body から title 取得 → models で item 生成 → put_item |
| `GET /todos` | `list_todos.handler` | 200 | scan → created_at 降順ソート |
| `GET /todos/{id}` | `get_todo.handler` | 200 / 404 | PK=TODO#{id} で get_item |
| `PUT /todos/{id}` | `update_todo.handler` | 200 / 404 | 動的 UpdateExpression 構築 → update_item |
| `DELETE /todos/{id}` | `delete_todo.handler` | 204 | PK=TODO#{id} で delete_item |

---

## 3. フロントエンド設計

### 3.1 セットアップ方法

`create-quasar` CLI で対話的に生成:

- Quasar App with Vite
- TypeScript
- Composition API
- Sass (sass-embedded)
- ESLint

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
services/api.ts          → axios インスタンス (baseURL: VITE_API_URL)
services/todo.service.ts → list(), get(id), create(data), update(id, data), delete(id)
```

### 3.4 コンポーネント構成

```
TodoPage.vue ← useTodos composable
  ├── TodoForm.vue     q-input (title) + q-btn (追加)
  └── TodoList.vue     q-list + q-spinner (loading) + 空状態メッセージ
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
| `.env.development` | `VITE_API_URL` | `http://localhost:3000/dev` |
| `.env.production` | `VITE_API_URL` | `<sam deploy の Outputs から取得>` |

---

## 4. Amplify Gen2 ホスティング

### 4.1 amplify.yml (リポジトリルート)

```yaml
version: 1
frontend:
  phases:
    preBuild:
      commands:
        - cd frontend
        - npm ci --cache .npm --prefer-offline
    build:
      commands:
        - cd frontend
        - echo "VITE_API_URL=$VITE_API_URL" > .env.production
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
- Amplify コンソールで環境変数 `VITE_API_URL` を設定
- SPA リダイレクトルール: `/<*>` → `/index.html` (200 Rewrite) を Amplify コンソールで設定

### 4.3 Amplify セットアップ手順

1. Amplify コンソール → 「Host web app」
2. Git リポジトリを接続、`main` ブランチ選択
3. `amplify.yml` を自動検出
4. 環境変数 `VITE_API_URL` を設定
5. SPA リダイレクトルールを追加

---

## 5. ローカル開発フロー

### 前提条件

- Docker Desktop (`sam local` に必要)
- AWS CLI 設定済み (`aws configure`)
- Python 3.12, Node.js 18+, SAM CLI

### 起動手順

```bash
# ターミナル 1: バックエンド
cd backend
sam build
sam local start-api --port 3000 --warm-containers EAGER

# ターミナル 2: フロントエンド
cd frontend
npm install
npx quasar dev
# → http://localhost:9000
```

- `sam local start-api` は実際の AWS DynamoDB (dev テーブル) に接続する
- 完全オフライン開発が必要な場合は DynamoDB Local (Docker) を別途導入

---

## 6. デプロイフロー

```
1. cd backend && sam build && sam deploy --guided  → API URL を取得
   (2回目以降: sam build && sam deploy)

2. Amplify コンソールで VITE_API_URL 環境変数に API URL を設定 (初回 or URL 変更時のみ)

3. git push → Amplify 自動ビルド・デプロイ
```

---

## 7. 実装順序

| # | タスク |
|---|--------|
| 1 | `backend/template.yaml` — SAM テンプレート |
| 2 | `backend/src/shared/` — 共通ユーティリティ |
| 3 | `backend/src/handlers/` — Lambda ハンドラー 5本 |
| 4 | バックエンド動作確認 (`sam build` → `sam local start-api` → curl) |
| 5 | `frontend/` — create-quasar で生成 |
| 6 | `frontend/src/types`, `services/` — 型定義・API 通信 |
| 7 | `frontend/src/composables/` — useTodos |
| 8 | `frontend/src/components/`, `pages/` — UI コンポーネント |
| 9 | 結合テスト (フロントエンド + バックエンド) |
| 10 | `amplify.yml`, `.gitignore`, `README.md` — プロジェクト整備 |

---

## 8. 検証方法

### バックエンド (curl)

```bash
# 作成
curl -s -X POST http://localhost:3000/dev/todos \
  -H "Content-Type: application/json" \
  -d '{"title":"テストTodo"}' | jq

# 一覧
curl -s http://localhost:3000/dev/todos | jq

# 更新
curl -s -X PUT http://localhost:3000/dev/todos/{id} \
  -H "Content-Type: application/json" \
  -d '{"completed":true}' | jq

# 削除
curl -s -X DELETE http://localhost:3000/dev/todos/{id}
```

### フロントエンド

- `npx quasar dev` でブラウザ確認
- Todo の追加・一覧表示・完了トグル・削除が動作すること

### デプロイ後

- Amplify URL にアクセス → API 経由で CRUD 操作が動作すること
