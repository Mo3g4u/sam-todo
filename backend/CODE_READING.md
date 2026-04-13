# Backend コードリーディングガイド

このドキュメントは、バックエンドのコードを上から順に読んで処理の流れを理解するためのガイドです。

---

## 読む順序

以下の順序で読むと理解しやすいです:

```
1. shared/models.py          ← データの形を知る
2. shared/dynamo_helper.py   ← DB 接続の仕組みを知る
3. shared/response_builder.py ← レスポンスの仕組みを知る
4. handlers/create_todo.py   ← 一番シンプルな CRUD (Create)
5. handlers/list_todos.py    ← Read (全件)
6. handlers/get_todo.py      ← Read (1件)
7. handlers/update_todo.py   ← 最も複雑な Update
8. handlers/delete_todo.py   ← 一番シンプルな Delete
```

---

## 1. shared/models.py — Todo データの形を決める

```python
import uuid
from datetime import datetime, timezone


def create_todo_item(title: str) -> dict:
    todo_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "PK": f"TODO#{todo_id}",
        "id": todo_id,
        "title": title,
        "completed": False,
        "created_at": now,
        "updated_at": now,
    }
```

### 解説

この関数は「新しい Todo を作るとき、どんなデータを DynamoDB に保存するか」を決めます。

| フィールド | 値の例 | 用途 |
|---|---|---|
| `PK` | `TODO#a1b2c3d4-...` | DynamoDB のパーティションキー。テーブル内でデータを一意に特定する |
| `id` | `a1b2c3d4-...` | API レスポンス用の ID。PK からプレフィックスを除いたもの |
| `title` | `買い物に行く` | ユーザーが入力した Todo のタイトル |
| `completed` | `False` | 新規作成時は必ず未完了 |
| `created_at` | `2026-04-10T12:00:00Z` | 作成日時 (UTC, ISO 8601 形式) |
| `updated_at` | `2026-04-10T12:00:00Z` | 更新日時 (作成時は created_at と同じ) |

**なぜ PK と id を分けるか**: DynamoDB のキー (`PK`) には `TODO#` プレフィックスを付けて他のデータ種別と区別できるようにしています。API レスポンスには `id` だけを返し、内部実装 (`PK`) をクライアントに見せません。

---

## 2. shared/dynamo_helper.py — DynamoDB への接続

```python
import os
import boto3

_table = None


def get_table():
    global _table
    table_name = os.environ["TABLE_NAME"]
    if _table is None or _table.table_name != table_name:
        endpoint = os.environ.get("DYNAMODB_ENDPOINT")
        if endpoint:
            dynamodb = boto3.resource(
                "dynamodb",
                endpoint_url=endpoint,
                region_name=os.environ.get("AWS_DEFAULT_REGION", "ap-northeast-1"),
                aws_access_key_id="dummy",
                aws_secret_access_key="dummy",
            )
        else:
            dynamodb = boto3.resource("dynamodb")
        _table = dynamodb.Table(table_name)
    return _table
```

### 解説

**役割**: DynamoDB テーブルへの接続オブジェクトを取得する。

**シングルトンパターン**: `_table` をグローバル変数に保持し、2 回目以降の呼び出しでは接続を再利用します。Lambda はコンテナが再利用されるため、初回接続のコストを 2 回目以降に回避できます。

**ローカル開発と AWS の切り替え**:

```
DYNAMODB_ENDPOINT が設定されている場合:
  → DynamoDB Local (Docker) に接続
  → ダミーの認証情報を使う (DynamoDB Local は認証不要だが boto3 が要求する)

DYNAMODB_ENDPOINT が未設定の場合:
  → AWS マネージドの DynamoDB に接続
  → Lambda の実行ロールの認証情報が自動的に使われる
```

**環境変数の出どころ**:
- `TABLE_NAME`: SAM テンプレートの `Globals.Function.Environment` で設定
- `DYNAMODB_ENDPOINT`: ローカル開発時は `env.json` で `http://host.docker.internal:8000` を設定

---

## 3. shared/response_builder.py — HTTP レスポンスの構築

```python
import json
import os
from decimal import Decimal


class _DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def _cors_headers() -> dict:
    allowed = os.environ.get("ALLOWED_ORIGINS", "http://localhost:9000").rstrip("/")
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": allowed,
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
    }


def success(body, status: int = 200) -> dict:
    return {
        "statusCode": status,
        "headers": _cors_headers(),
        "body": json.dumps(body, cls=_DecimalEncoder),
    }


def error(message: str, status: int = 400) -> dict:
    return {
        "statusCode": status,
        "headers": _cors_headers(),
        "body": json.dumps({"error": message}),
    }
```

### 解説

**役割**: 全ハンドラーが統一的なフォーマットで HTTP レスポンスを返すためのヘルパー。

**API Gateway が期待するレスポンス形式**:

```python
{
    "statusCode": 200,           # HTTP ステータスコード
    "headers": { ... },          # レスポンスヘッダー
    "body": '{"key": "value"}'   # JSON 文字列 (dict ではない)
}
```

`body` は辞書ではなく **JSON 文字列** でなければなりません。`json.dumps()` で変換しています。

**_DecimalEncoder**: DynamoDB は数値を Python の `Decimal` 型で返します。`json.dumps()` は `Decimal` をそのまま処理できないので、`float` に変換するカスタムエンコーダーを使います。

**CORS ヘッダー**: ブラウザのセキュリティ機能 (同一オリジンポリシー) を通過するために必要です。`ALLOWED_ORIGINS` 環境変数で許可するドメインを制御します。`.rstrip("/")` は末尾スラッシュを除去するためのもの (ブラウザの Origin ヘッダーにはスラッシュが付かないため)。

---

## 4. handlers/create_todo.py — Todo の作成

```python
import json
from shared.dynamo_helper import get_table
from shared.models import create_todo_item
from shared.response_builder import error, success


def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return error("Invalid JSON body")

    title = body.get("title")
    if not title:
        return error("title is required")

    try:
        item = create_todo_item(title)
        table = get_table()
        table.put_item(Item=item)
        item.pop("PK")
        return success(item, status=201)
    except Exception as e:
        return error(str(e), status=500)
```

### 処理フロー

```
POST /todos  { "title": "買い物に行く" }

1. event["body"] から JSON を解析
   → body = {"title": "買い物に行く"}

2. title のバリデーション
   → 空や未指定なら 400 エラー

3. create_todo_item("買い物に行く") で Todo データを生成
   → { "PK": "TODO#xxx", "id": "xxx", "title": "買い物に行く", "completed": False, ... }

4. DynamoDB に保存 (put_item)

5. PK を除去して 201 レスポンスを返す
   → { "id": "xxx", "title": "買い物に行く", "completed": false, ... }
```

**`event` の中身**: API Gateway が Lambda に渡すイベントオブジェクト。`event["body"]` にリクエストボディが JSON 文字列として入っています。

**`context`**: Lambda の実行環境情報 (残り時間、リクエスト ID など)。この関数では使いません。

**`item.pop("PK")`**: DynamoDB の内部キーをレスポンスから除去。クライアントには `id` だけを見せます。

---

## 5. handlers/list_todos.py — Todo 一覧の取得

```python
from shared.dynamo_helper import get_table
from shared.response_builder import error, success


def handler(event, context):
    try:
        table = get_table()
        resp = table.scan()
        items = resp.get("Items", [])

        for item in items:
            item.pop("PK", None)

        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return success(items)
    except Exception as e:
        return error(str(e), status=500)
```

### 処理フロー

```
GET /todos

1. table.scan() でテーブル全件取得
   → { "Items": [ {...}, {...}, ... ] }

2. 各アイテムから PK を除去

3. created_at の降順 (新しい順) にソート

4. 200 レスポンスで配列を返す
   → [ {"id": "...", "title": "..."}, ... ]
```

**`table.scan()`**: テーブルの全件を取得する操作。MVP の小規模データでは問題ないが、大量データには向きません (将来的には Query + GSI に移行)。

**`item.pop("PK", None)`**: `None` を指定すると、PK が存在しなくてもエラーにならない (`pop()` のデフォルト値)。

---

## 6. handlers/get_todo.py — 単一 Todo の取得

```python
from shared.dynamo_helper import get_table
from shared.response_builder import error, success


def handler(event, context):
    todo_id = event["pathParameters"]["id"]

    try:
        table = get_table()
        resp = table.get_item(Key={"PK": f"TODO#{todo_id}"})
        item = resp.get("Item")

        if not item:
            return error("Todo not found", status=404)

        item.pop("PK", None)
        return success(item)
    except Exception as e:
        return error(str(e), status=500)
```

### 処理フロー

```
GET /todos/abc-123

1. URL パスから id を取得
   → event["pathParameters"]["id"] = "abc-123"

2. PK を組み立てて get_item
   → Key={"PK": "TODO#abc-123"}

3. 結果がなければ 404、あれば PK を除去して 200 で返す
```

**`event["pathParameters"]`**: API Gateway がパスパラメータ (`{id}`) を辞書として渡します。

**`get_item` vs `scan`**: `get_item` は PK を指定して 1 件取得。`scan` と違い、テーブル全体を走査しないので高速です。

---

## 7. handlers/update_todo.py — Todo の更新

```python
import json
from datetime import datetime, timezone
from shared.dynamo_helper import get_table
from shared.response_builder import error, success


def handler(event, context):
    todo_id = event["pathParameters"]["id"]

    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return error("Invalid JSON body")

    try:
        table = get_table()
        existing = table.get_item(Key={"PK": f"TODO#{todo_id}"}).get("Item")
        if not existing:
            return error("Todo not found", status=404)

        update_expr_parts = []
        expr_names = {}
        expr_values = {}

        if "title" in body:
            update_expr_parts.append("#t = :t")
            expr_names["#t"] = "title"
            expr_values[":t"] = body["title"]

        if "completed" in body:
            update_expr_parts.append("#c = :c")
            expr_names["#c"] = "completed"
            expr_values[":c"] = body["completed"]

        if not update_expr_parts:
            return error("No fields to update")

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        update_expr_parts.append("updated_at = :u")
        expr_values[":u"] = now

        resp = table.update_item(
            Key={"PK": f"TODO#{todo_id}"},
            UpdateExpression="SET " + ", ".join(update_expr_parts),
            ExpressionAttributeNames=expr_names if expr_names else None,
            ExpressionAttributeValues=expr_values,
            ReturnValues="ALL_NEW",
        )

        item = resp["Attributes"]
        item.pop("PK", None)
        return success(item)
    except Exception as e:
        return error(str(e), status=500)
```

### 処理フロー

```
PUT /todos/abc-123  { "completed": true }

1. URL パスから id を取得
2. リクエストボディを解析
3. 既存データの存在確認 (get_item)
   → なければ 404

4. UpdateExpression を動的に組み立て:
   body に "title" がある    → "#t = :t" を追加
   body に "completed" がある → "#c = :c" を追加
   常に                      → "updated_at = :u" を追加

   結果例: "SET #c = :c, updated_at = :u"

5. update_item を実行して更新後のデータを取得 (ReturnValues="ALL_NEW")
6. PK を除去して 200 で返す
```

**なぜ `#t`, `#c` を使うか**: DynamoDB の `title`, `completed` は予約語ではないが、`ExpressionAttributeNames` を使うのはベストプラクティスです。将来フィールド名が予約語と衝突しても壊れません。

**動的 UpdateExpression**: リクエストに含まれるフィールドだけを更新します。`title` だけ、`completed` だけ、両方、いずれにも対応できます。

**`ReturnValues="ALL_NEW"`**: 更新後のアイテム全体を DynamoDB が返してくれます。これにより、更新後のデータを別途取得する必要がありません。

---

## 8. handlers/delete_todo.py — Todo の削除

```python
from shared.dynamo_helper import get_table
from shared.response_builder import error, success


def handler(event, context):
    todo_id = event["pathParameters"]["id"]

    try:
        table = get_table()
        table.delete_item(Key={"PK": f"TODO#{todo_id}"})
        return success("", status=204)
    except Exception as e:
        return error(str(e), status=500)
```

### 処理フロー

```
DELETE /todos/abc-123

1. URL パスから id を取得
2. delete_item で削除
3. 204 (No Content) を返す
```

**存在しない ID でも 204**: `delete_item` は対象が存在しなくてもエラーにならないため、常に 204 を返します。これは REST API の慣例に従った設計 (冪等性)。

---

## テストの読み方

### conftest.py — 共通フィクスチャ

```python
@pytest.fixture
def dynamo_table(aws_env):
    with mock_aws():                    # AWS をモック化
        dynamo_helper._table = None     # シングルトンをリセット
        client = boto3.client("dynamodb", ...)
        client.create_table(...)        # モック DynamoDB にテーブル作成
        yield                           # テスト実行
        dynamo_helper._table = None     # 後片付け
```

**moto**: AWS サービスをメモリ上でモックするライブラリ。実際の AWS に接続せずにテストできます。

**`yield`**: テストの実行を挟んで前後処理を行う (セットアップ → テスト → クリーンアップ)。

### テストの共通パターン

```python
@mock_aws                               # このテストメソッド内で AWS をモック化
def test_xxx(self, dynamo_table):        # conftest の dynamo_table フィクスチャを使用
    # 1. 準備 (Arrange): テストデータを作成
    create_handler({"body": json.dumps({"title": "テスト"})}, None)

    # 2. 実行 (Act): テスト対象を呼び出す
    resp = handler(event, None)

    # 3. 検証 (Assert): 期待する結果を確認
    assert resp["statusCode"] == 200
```
