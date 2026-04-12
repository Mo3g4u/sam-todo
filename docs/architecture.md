# SAM Todo App アーキテクチャドキュメント

## 1. システム全体構成

![Architecture](../generated-diagrams/architecture.png)

| レイヤー | 技術 | 役割 |
|---|---|---|
| フロントエンド | Vue 3 + Quasar v2 (TypeScript) | SPA、ユーザー操作 |
| ホスティング | AWS Amplify Gen2 | フロントエンド配信、自動デプロイ |
| API | Amazon API Gateway HTTP API v2 | REST エンドポイント、CORS 制御 |
| コンピュート | AWS Lambda (Python 3.12, arm64) | CRUD ビジネスロジック |
| データベース | Amazon DynamoDB (オンデマンド) | Todo データ永続化 |
| IaC | AWS SAM | インフラ定義・デプロイ |

---

## 2. バックエンド処理フロー

### 2.1 リクエストの流れ

```
Browser → API Gateway (HTTP API v2) → Lambda Handler → DynamoDB
                                           ↓
                                     shared/dynamo_helper.py  (テーブル接続)
                                     shared/models.py         (データ生成)
                                     shared/response_builder.py (レスポンス構築)
```

### 2.2 エンドポイントと処理内容

| メソッド | パス | ハンドラー | 処理 |
|---|---|---|---|
| POST | `/todos` | `create_todo.handler` | JSON body から `title` 取得 → UUID 生成 → `put_item` → 201 |
| GET | `/todos` | `list_todos.handler` | `scan` → PK 除去 → `created_at` 降順ソート → 200 |
| GET | `/todos/{id}` | `get_todo.handler` | `get_item(PK=TODO#{id})` → 200 / 404 |
| PUT | `/todos/{id}` | `update_todo.handler` | 存在確認 → 動的 `UpdateExpression` 構築 → `update_item` → 200 / 404 |
| DELETE | `/todos/{id}` | `delete_todo.handler` | `delete_item(PK=TODO#{id})` → 204 |

### 2.3 共通モジュール (shared/)

```
shared/
├── dynamo_helper.py    テーブルリソースのシングルトン取得
│                       DYNAMODB_ENDPOINT があればローカル接続 (ダミー認証)
│                       なければ AWS マネージド接続
│
├── models.py           create_todo_item(title) → Todo dict 生成
│                       UUID v4, PK="TODO#<uuid>", ISO 8601 タイムスタンプ
│
└── response_builder.py success(body, status=200) → API Gateway レスポンス
                        error(message, status=400)
                        Decimal → float 変換の JSON エンコーダー内蔵
```

### 2.4 DynamoDB テーブル設計

```
テーブル名: todo-table-dev
キー:      PK (String) = "TODO#<uuid>"

属性:
  PK          "TODO#<uuid>"       ← パーティションキー (API レスポンスからは除去)
  id          "<uuid>"            ← API レスポンス用
  title       "買い物に行く"
  completed   false
  created_at  "2026-04-10T12:00:00Z"
  updated_at  "2026-04-10T12:00:00Z"
```

- GSI なし (MVP、小規模のため Scan で十分)
- BillingMode: PAY_PER_REQUEST (オンデマンド)

### 2.5 エラーハンドリング

全ハンドラーに try/except を設置。DynamoDB 接続エラー等の未処理例外は `500` で返す。

```python
# 例: list_todos.py
try:
    table = get_table()
    resp = table.scan()
    ...
    return success(items)
except Exception as e:
    return error(str(e), status=500)
```

---

## 3. フロントエンド処理フロー

![Frontend Flow](../generated-diagrams/frontend-flow.png)

### 3.1 コンポーネント構成

```
App.vue                     ← q-layout + q-header + q-page-container
└── router-view
    └── TodoPage.vue        ← useTodos() composable でデータ管理
        ├── TodoForm.vue    ← q-input + q-btn (追加ボタン)
        └── TodoList.vue    ← q-spinner / 空メッセージ / q-list
            └── TodoItem.vue ← q-checkbox + タイトル + 削除ボタン (×N)
```

### 3.2 データフロー

```
[ユーザー操作]
    ↓
TodoForm / TodoItem          ← emit('add', title) / emit('toggle', todo) / emit('remove', id)
    ↓
TodoPage.vue                 ← イベントを composable の関数に接続
    ↓
useTodos() composable        ← リアクティブ state: todos, loading, error
    ↓                          関数: fetchTodos, addTodo, toggleTodo, removeTodo
todoService                  ← list(), create(), update(), remove()
    ↓
api.ts (axios)               ← baseURL: VITE_API_URL
    ↓
API Gateway → Lambda → DynamoDB
```

### 3.3 状態管理 (useTodos composable)

| 状態 | 型 | 用途 |
|---|---|---|
| `todos` | `Ref<Todo[]>` | Todo 一覧 |
| `loading` | `Ref<boolean>` | API 通信中フラグ |
| `error` | `Ref<string \| null>` | エラーメッセージ (日本語) |

| 関数 | 処理 |
|---|---|
| `fetchTodos()` | `todoService.list()` → `todos` に格納 |
| `addTodo(title)` | `todoService.create({title})` → `todos` の先頭に追加 |
| `toggleTodo(todo)` | `todoService.update(id, {completed: !completed})` → 該当要素を差し替え |
| `removeTodo(id)` | `todoService.remove(id)` → `todos` からフィルター除去 |

### 3.4 型定義

```typescript
interface Todo {
  id: string;
  title: string;
  completed: boolean;
  created_at: string;
  updated_at?: string;
}

interface CreateTodoRequest { title: string; }
interface UpdateTodoRequest { title?: string; completed?: boolean; }
```

---

## 4. ローカル開発環境

```
┌─────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│ Quasar Dev       │    │ SAM Local API        │    │ DynamoDB Local      │
│ localhost:9000   │───→│ localhost:3000        │───→│ localhost:8000      │
│ (HMR)           │    │ (Docker + Lambda)     │    │ (Docker, in-memory) │
└─────────────────┘    └──────────────────────┘    └─────────────────────┘
```

### 起動コマンド

```bash
make dev-backend     # DynamoDB Local 起動 → テーブル作成 → sam build → sam local start-api
make dev-frontend    # Quasar dev server (port 9000)
```

### ポイント

- `backend/env.json` で `DYNAMODB_ENDPOINT=http://host.docker.internal:8000` を Lambda コンテナに渡す
- `dynamo_helper.py` が `DYNAMODB_ENDPOINT` 環境変数を検出するとローカル接続 (ダミー認証) に切り替え
- DynamoDB Local は in-memory モード (`-inMemory`) のため、再起動するとデータが消える
- テーブル作成は `scripts/create-table.sh` で自動実行

---

## 5. CI/CD パイプライン

![CI/CD Pipeline](../generated-diagrams/cicd-pipeline.png)

### 5.1 ワークフロー一覧

| ワークフロー | トリガー | 処理 |
|---|---|---|
| `backend.yml` | `backend/**` への push/PR | Ruff lint → pytest → (main のみ) SAM deploy |
| `frontend.yml` | `frontend/**` への push/PR | ESLint → Prettier → Vitest → npm audit → audit signatures |
| `dependency-review.yml` | 全 PR | 脆弱性 (high+) + 禁止ライセンス (GPL/AGPL) チェック |

### 5.2 デプロイフロー

```
Developer
  │
  ├─ git push (backend/**)
  │   └─ GitHub Actions (backend.yml)
  │       ├─ test job: ruff check → ruff format → pytest
  │       └─ deploy job (main only):
  │           ├─ OIDC で AWS AssumeRole
  │           ├─ ROLLBACK_COMPLETE スタック自動削除
  │           └─ sam deploy → CloudFormation → Lambda + API Gateway + DynamoDB
  │
  └─ git push (frontend/**)
      ├─ GitHub Actions (frontend.yml): lint → test → audit
      └─ Amplify Hosting: 自動ビルド・デプロイ (amplify.yml)
```

### 5.3 AWS 認証

- GitHub → AWS 間は **OIDC** (OpenID Connect) で認証
- 長期 Access Key は使用しない
- IAM ロール: `github-actions-sam-todo` (Mo3g4u/sam-todo の main ブランチのみ AssumeRole 可能)
- GitHub Secrets: `AWS_ROLE_ARN` のみ

---

## 6. サプライチェーン防御

| 防御策 | 内容 |
|---|---|
| Actions SHA ピン留め | 全 Actions をフルレングスコミット SHA で固定 |
| Dependabot | npm / pip / github-actions の週次自動更新 PR |
| Dependency Review | PR 時に high 以上の脆弱性 + GPL/AGPL ライセンスを拒否 |
| npm audit | CI で `npm audit --audit-level=high` 実行 |
| audit signatures | `npm audit signatures` でパッケージ真正性検証 |
| ignore-scripts | `.npmrc` で `ignore-scripts=true`、postinstall 攻撃を防止 |

---

## 7. テスト戦略

### バックエンド (pytest + moto)

```
tests/
├── conftest.py                 ← dynamo_table fixture (mock AWS DynamoDB)
└── unit/
    ├── handlers/               ← Lambda ハンドラーの CRUD テスト
    │   ├── test_create_todo.py   (201, 400 バリデーション)
    │   ├── test_list_todos.py    (空リスト, ソート順)
    │   ├── test_get_todo.py      (200, 404)
    │   ├── test_update_todo.py   (title更新, completed更新, 404)
    │   └── test_delete_todo.py   (204, 存在しないIDも204)
    └── shared/                 ← 共通ユーティリティのテスト
        ├── test_models.py        (フィールド, UUID一意性, タイムスタンプ)
        ├── test_response_builder.py (ステータス, Decimal, ヘッダー)
        └── test_dynamo_helper.py (テーブル取得, エンドポイント, KeyError)
```

### フロントエンド (Vitest + happy-dom)

```
tests/unit/
├── services/
│   └── todo.service.test.ts    ← axios を mock して 5 メソッドをテスト
└── composables/
    └── useTodos.test.ts        ← todoService を mock して状態管理をテスト
```

### E2E (Playwright)

```
e2e/
└── todo_app.py                 ← ブラウザで CRUD 全操作を自動テスト
```

---

## 8. ディレクトリ構成

```
sam-todo/
├── backend/
│   ├── template.yaml               SAM テンプレート
│   ├── docker-compose.yml           DynamoDB Local
│   ├── env.json                     ローカル開発用環境変数
│   ├── scripts/create-table.sh      テーブル自動作成
│   ├── pyproject.toml               pytest + Ruff 設定
│   ├── requirements-dev.txt         開発依存 (pytest, moto, ruff)
│   ├── src/
│   │   ├── requirements.txt         Lambda 依存 (boto3)
│   │   ├── handlers/                Lambda ハンドラー x5
│   │   └── shared/                  共通ユーティリティ
│   └── tests/                       pytest テスト
├── frontend/
│   ├── package.json                 依存 + スクリプト
│   ├── quasar.config.ts             Quasar 設定
│   ├── vitest.config.ts             Vitest 設定
│   ├── .eslintrc.cjs / .prettierrc  Lint + Format 設定
│   ├── .npmrc                       ignore-scripts=true
│   ├── .env.development             VITE_API_URL=http://localhost:3000
│   ├── src/
│   │   ├── App.vue                  ルートレイアウト
│   │   ├── pages/TodoPage.vue       メインページ
│   │   ├── components/              UI コンポーネント x3
│   │   ├── composables/useTodos.ts  状態管理
│   │   ├── services/                API 通信レイヤー
│   │   ├── types/todo.ts            TypeScript 型定義
│   │   └── router/                  Vue Router 設定
│   └── tests/                       Vitest テスト
├── e2e/                             Playwright E2E テスト
├── infra/github-oidc.yaml           OIDC 用 CloudFormation
├── .github/
│   ├── workflows/                   CI/CD ワークフロー x3
│   └── dependabot.yml               自動依存更新
├── amplify.yml                      Amplify ビルド設定
├── Makefile                         開発コマンド
├── CLAUDE.md                        Claude Code ガイダンス
└── docs/
    ├── design.md                    設計ドキュメント
    └── architecture.md              本ドキュメント
```
