# Control Tower CT.LAMBDA.PV.2 と DefinitionBody 対応の解説

## この文書の目的

本プロジェクトでは、AWS へのデプロイ時に `template-deploy.yaml` という特別なテンプレートを使っています。通常の SAM テンプレート (`template.yaml`) と何が違い、なぜ必要なのかを解説します。

---

## 1. 前提知識

### 1.1 API Gateway と Lambda の関係

Todo アプリのバックエンドは以下の流れでリクエストを処理します:

```
ブラウザ → API Gateway → Lambda 関数 → DynamoDB
```

ここで重要なのは、**API Gateway が Lambda 関数を「呼び出す」ためには、Lambda 側に「呼び出してよい」という許可が必要**ということです。

これは家に例えると:
- Lambda 関数 = 家
- API Gateway = 訪問者
- 許可 = 「この訪問者は入ってよい」という玄関の鍵

### 1.2 Lambda のリソースベースポリシー

Lambda 関数には**リソースベースポリシー**という仕組みがあります。これは「誰がこの関数を呼び出してよいか」を定義するものです。

```json
{
  "Effect": "Allow",
  "Principal": { "Service": "apigateway.amazonaws.com" },
  "Action": "lambda:InvokeFunction",
  "Resource": "arn:aws:lambda:...:function:CreateTodoFunction"
}
```

この許可を追加する API アクション (操作) が **`lambda:AddPermission`** です。

### 1.3 SAM の自動動作

AWS SAM (Serverless Application Model) は開発者の手間を減らすために、テンプレートに以下のように書くと:

```yaml
CreateTodoFunction:
  Type: AWS::Serverless::Function
  Properties:
    Events:
      Api:
        Type: HttpApi
        Properties:
          Path: /todos
          Method: POST
```

裏側で自動的に以下を生成します:
1. API Gateway のルート (POST /todos)
2. API Gateway → Lambda の連携 (Integration)
3. **Lambda のリソースベースポリシー** (`lambda:AddPermission` を実行)

つまり `Events` を書くだけで、API Gateway → Lambda の接続が自動的に完成します。

### 1.4 AWS Control Tower と SCP

**AWS Control Tower** は、企業が複数の AWS アカウントを安全に管理するためのサービスです。「全アカウントでこの操作は禁止」といったルールを一元管理できます。

そのルールの実体が **SCP (Service Control Policy)** です。SCP は IAM ポリシーより強力で、**どんなに強い IAM 権限を持っていても SCP で禁止されていれば実行できません**。

```
権限の評価順:
  SCP (組織レベル) → IAM ポリシー (アカウントレベル)

  SCP で Deny → IAM で Allow していても → 結果: Deny
```

---

## 2. 問題: CT.LAMBDA.PV.2

### 2.1 このルールは何か

Control Tower には `CT.LAMBDA.PV.2` というプリセットルールがあります。正式名称は「Lambda 関数へのクロスアカウントアクセスを制限する」です。

このルールの目的は、**外部の AWS アカウントから自分の Lambda 関数を呼び出されることを防ぐ**ことです。

### 2.2 SCP の中身

SCP は以下のように動作します:

```
lambda:AddPermission が呼ばれたとき:
  許可する条件:
    - 呼び出し元が「自分のアカウントの IAM エンティティ」の場合
  拒否する条件:
    - 上記以外すべて
```

### 2.3 なぜ問題になるか

SAM が自動生成する `lambda:AddPermission` は、以下のように設定します:

```
「apigateway.amazonaws.com (API Gateway サービス) が Lambda を呼び出してよい」
```

ここで許可する対象 (プリンシパル) は `apigateway.amazonaws.com` という **AWS サービスプリンシパル**です。これは「自分のアカウントの IAM エンティティ」ではないため、**SCP に拒否されます**。

```
SAM が実行: lambda:AddPermission(Principal=apigateway.amazonaws.com)
                                               ↓
SCP の判定: apigateway.amazonaws.com は IAM エンティティではない
                                               ↓
結果: Deny → デプロイ失敗
```

同じアカウント内の API Gateway であっても、SCP は区別できずにブロックしてしまいます。

### 2.4 実際のエラーメッセージ

```
CREATE_FAILED  AWS::Lambda::Permission  CreateTodoFunctionApiPermission

User: arn:aws:sts::456788081138:role/github-actions-sam-todo/GitHubActions
is not authorized to perform: lambda:AddPermission on resource:
arn:aws:lambda:ap-northeast-1:456788081138:function:sam-todo-CreateTodoFunction-*
```

IAM ポリシーシミュレーションでも確認:

```json
{
  "EvalDecision": "implicitDeny",
  "OrganizationsDecisionDetail": {
    "AllowedByOrganizations": false
  }
}
```

`AllowedByOrganizations: false` = SCP でブロックされている、という意味です。

---

## 3. 解決策: AssumeRole 方式

### 3.1 考え方の転換

**通常の方式 (Lambda リソースベースポリシー)**:
```
API Gateway →「Lambda さん、呼んでいいですか？」→ Lambda が許可を判定
```

**AssumeRole 方式**:
```
API Gateway →「Lambda を呼ぶ権限を持つ IAM ロールになる」→ そのロールで Lambda を呼ぶ
```

つまり、Lambda 側に「誰が呼んでよいか」を設定する (`lambda:AddPermission`) のではなく、API Gateway が「Lambda を呼べる IAM ロール」を着ることで呼び出します。

### 3.2 AssumeRole (ロールの引き受け) とは

IAM ロールは「権限の入った帽子」のようなものです。普段の自分とは別の権限を、**帽子をかぶることで一時的に得る**仕組みが AssumeRole です。

```
通常の IAM ユーザー/サービス:
  自分自身の権限だけを持つ

AssumeRole:
  「Lambda を呼べる権限」が入った帽子をかぶる → その権限が一時的に使える
```

ただし、帽子は誰でもかぶれるわけではありません。帽子 (ロール) 側に**「誰がかぶってよいか」を定義する**のが**信頼ポリシー (Trust Policy)** です。

### 3.3 信頼ポリシーの仕組み

信頼ポリシーは「この帽子を誰がかぶれるか」を定義します:

```
┌─────────────────────────────────────────────────────┐
│ ApiGatewayInvokeRole (帽子)                          │
│                                                     │
│ 信頼ポリシー (誰がかぶれるか):                          │
│   → apigateway.amazonaws.com がかぶれる              │
│                                                     │
│ 権限ポリシー (かぶると何ができるか):                     │
│   → Lambda 関数を呼び出せる                           │
└─────────────────────────────────────────────────────┘
```

具体的な流れ:

```
1. リクエストが API Gateway に届く

2. API Gateway が AWS に問い合わせる:
   「ApiGatewayInvokeRole をかぶりたいのですが」

3. AWS が信頼ポリシーをチェック:
   「apigateway.amazonaws.com はかぶってよい」→ OK

4. API Gateway が一時的な認証情報を受け取る
   (期限付きの Access Key / Secret Key / Session Token)

5. その認証情報を使って Lambda を呼び出す
   → Lambda 側にリソースベースポリシーは不要
   → lambda:AddPermission も不要
```

### 3.4 IAM ロールの定義

`template-deploy.yaml` で以下のロールを作成します:

```yaml
ApiGatewayInvokeRole:
  Type: AWS::IAM::Role
  Properties:
    # 信頼ポリシー: 誰がこの帽子をかぶれるか
    AssumeRolePolicyDocument:
      Statement:
        - Effect: Allow
          Principal:
            Service: apigateway.amazonaws.com   # ← API Gateway サービスがかぶれる
          Action: sts:AssumeRole

    # 権限ポリシー: かぶると何ができるか
    Policies:
      - PolicyName: InvokeLambdaPolicy
        PolicyDocument:
          Statement:
            - Effect: Allow
              Action: lambda:InvokeFunction     # ← Lambda を呼び出せる
              Resource:
                - !GetAtt CreateTodoFunction.Arn
                - !GetAtt ListTodosFunction.Arn
                # ... (5 関数すべて)
```

まとめると:

| ポリシー | 意味 | 設定内容 |
|---|---|---|
| **信頼ポリシー** | 誰がこのロールをかぶれるか | `apigateway.amazonaws.com` |
| **権限ポリシー** | かぶると何ができるか | 5 つの Lambda 関数を `InvokeFunction` |

### 3.3 DefinitionBody で API Gateway にロールを指定

通常の SAM `Events` では IAM ロールを指定できません。代わりに OpenAPI 仕様 (DefinitionBody) で API Gateway の各ルートに `credentials` (使用するロール) を明示指定します:

```yaml
TodoApi:
  Type: AWS::Serverless::HttpApi
  Properties:
    DefinitionBody:
      openapi: "3.0.1"
      paths:
        /todos:
          post:
            x-amazon-apigateway-integration:
              type: aws_proxy
              httpMethod: POST
              uri: ...Lambda 関数の ARN...
              credentials: ...ApiGatewayInvokeRole の ARN...    # ← ここがポイント
              payloadFormatVersion: "2.0"
```

`credentials` に IAM ロールの ARN を指定すると:
- API Gateway はリクエストを受けたとき、このロールを AssumeRole する
- そのロールの権限で Lambda を呼び出す
- Lambda 側にリソースベースポリシー (`lambda:AddPermission`) は不要

### 3.4 なぜ SCP を回避できるか

```
通常方式:
  lambda:AddPermission を実行 → SCP が拒否 → デプロイ失敗

AssumeRole 方式:
  iam:CreateRole を実行 → SCP で制限されていない → 成功
  API Gateway が IAM ロールで Lambda を呼ぶ → lambda:AddPermission 不要 → 成功
```

`lambda:AddPermission` というアクション自体を使わないので、SCP のルールに抵触しません。

---

## 4. なぜテンプレートが 2 つ必要か

### 4.1 SAM local の制限

`sam local start-api` はローカルで API Gateway をエミュレートするツールですが、DefinitionBody 内の CloudFormation 関数 (`Fn::Sub`, `Fn::GetAtt` など) を解決できません:

```
# sam local start-api 実行時のエラー
Error: sequence item 1: expected str instance, collections.OrderedDict found
```

一方、SAM `Events` はローカルで正しく動作します。

### 4.2 テンプレートの使い分け

```
ローカル開発 (sam local start-api)
  → template.yaml (Events ベース)
  → lambda:AddPermission は SAM local では実行されないので問題なし

AWS デプロイ (GitHub Actions → sam deploy)
  → template-deploy.yaml (DefinitionBody + IAM ロール)
  → lambda:AddPermission を使わないので SCP に抵触しない
```

| | template.yaml | template-deploy.yaml |
|---|---|---|
| 用途 | ローカル開発 | AWS デプロイ |
| ルーティング | SAM Events (自動) | OpenAPI DefinitionBody (手動) |
| Lambda 呼び出し権限 | 不要 (ローカル) | IAM ロール (AssumeRole) |
| Lambda::Permission | 生成されるが未使用 | 生成されない |
| `sam local` 互換 | OK | NG (CloudFormation 関数が解決できない) |

### 4.3 Lambda 関数の定義は共通

2 つのテンプレートで Lambda 関数の定義 (ハンドラー、CodeUri、ポリシー) は同一です。違いは「ルーティングの定義方法」と「Lambda 呼び出し権限の付与方法」のみです。

---

## 5. template-deploy.yaml 全行解説

実際のテンプレート (`backend/template-deploy.yaml`) に一行ずつコメントを付けたものです。

```yaml
# ===== テンプレートの基本情報 =====

AWSTemplateFormatVersion: "2010-09-09"
# CloudFormation テンプレートのバージョン (この値は固定)

Transform: AWS::Serverless-2016-10-31
# SAM (Serverless Application Model) の変換を有効にする
# これにより AWS::Serverless::Function などの SAM 専用リソースが使える

Description: SAM Todo App Backend (AWS Deployment)
# CloudFormation スタックの説明文 (コンソールに表示される)

# ===== パラメータ (デプロイ時に外から渡せる値) =====

Parameters:
  FrontendUrl:
    Type: String                 # 文字列型
    Default: ""                  # デフォルトは空 (未設定でもデプロイ可能)
    Description: Amplify frontend URL (e.g. https://main.xxxx.amplifyapp.com)
    # GitHub Secrets の FRONTEND_URL から sam deploy --parameter-overrides で渡す

# ===== 条件 (パラメータに基づく分岐) =====

Conditions:
  HasFrontendUrl: !Not [!Equals [!Ref FrontendUrl, ""]]
  # FrontendUrl が空文字でなければ true
  # !Ref FrontendUrl → パラメータの値を取得
  # !Equals [..., ""]  → 空文字と比較
  # !Not [...]         → 結果を反転
  # → FrontendUrl が設定されていれば HasFrontendUrl = true

# ===== グローバル設定 (全 Lambda 関数に適用) =====

Globals:
  Function:
    Runtime: python3.12          # Lambda の実行環境 (Python 3.12)
    Architectures:
      - arm64                    # Graviton2 (ARM) を使用。x86 より安価で高速
    Timeout: 10                  # Lambda の最大実行時間 (10秒)
    MemorySize: 128              # Lambda のメモリ割り当て (128MB、最小値)
    Environment:
      Variables:
        TABLE_NAME: !Ref TodoTable
        # DynamoDB テーブル名。!Ref TodoTable で後述の TodoTable リソースの
        # テーブル名 (todo-table-dev) に解決される

        DYNAMODB_ENDPOINT: ""
        # ローカル開発時は env.json で上書きして DynamoDB Local に接続
        # AWS デプロイ時は空文字 → dynamo_helper.py が AWS マネージド DynamoDB を使用

        ALLOWED_ORIGINS: !If [HasFrontendUrl, !Ref FrontendUrl, "http://localhost:9000"]
        # CORS で許可するオリジン。response_builder.py が参照する
        # !If [条件, true時の値, false時の値]
        # → FrontendUrl が設定されていれば Amplify の URL、未設定なら localhost

# ===== リソース定義 =====

Resources:

  # ----- API Gateway が Lambda を呼ぶための IAM ロール -----
  # これが Control Tower CT.LAMBDA.PV.2 を回避するための核心部分

  ApiGatewayInvokeRole:
    Type: AWS::IAM::Role         # IAM ロール (権限の帽子) を作成
    Properties:

      # 信頼ポリシー: 「誰がこの帽子をかぶれるか」
      AssumeRolePolicyDocument:
        Version: "2012-10-17"    # ポリシー言語のバージョン (この値は固定)
        Statement:
          - Effect: Allow        # 許可する
            Principal:
              Service: apigateway.amazonaws.com
              # ↑ API Gateway サービスが、このロールを AssumeRole できる
            Action: sts:AssumeRole
            # ↑ 「ロールを引き受ける」というアクションを許可

      # 権限ポリシー: 「この帽子をかぶると何ができるか」
      Policies:
        - PolicyName: InvokeLambdaPolicy     # ポリシーの名前 (任意)
          PolicyDocument:
            Version: "2012-10-17"
            Statement:
              - Effect: Allow                # 許可する
                Action: lambda:InvokeFunction
                # ↑ Lambda 関数を呼び出すアクション
                Resource:
                  - !GetAtt CreateTodoFunction.Arn   # POST /todos 用関数
                  - !GetAtt ListTodosFunction.Arn    # GET /todos 用関数
                  - !GetAtt GetTodoFunction.Arn      # GET /todos/{id} 用関数
                  - !GetAtt UpdateTodoFunction.Arn   # PUT /todos/{id} 用関数
                  - !GetAtt DeleteTodoFunction.Arn   # DELETE /todos/{id} 用関数
                  # !GetAtt は他のリソースの属性を取得する関数
                  # .Arn で Lambda 関数の ARN (一意な識別子) を取得
                  # → この 5 関数だけを呼び出せる (最小権限の原則)

  # ----- API Gateway (HTTP API v2) -----

  TodoApi:
    Type: AWS::Serverless::HttpApi   # SAM の HTTP API リソース
    Properties:
      StageName: dev                 # ステージ名。URL に /dev として含まれる

      # DefinitionBody: OpenAPI (Swagger) 仕様でルーティングを定義
      # SAM Events の代わりにこれを使う理由:
      #   Events → lambda:AddPermission が自動生成される → SCP で拒否
      #   DefinitionBody → credentials で IAM ロールを指定 → lambda:AddPermission 不要
      DefinitionBody:
        openapi: "3.0.1"             # OpenAPI 仕様のバージョン
        info:
          title: SAM Todo API        # API の名前
          version: "1.0"             # API のバージョン

        # CORS プリフライト (OPTIONS リクエスト) の自動処理設定
        # ブラウザが POST/PUT/DELETE 前に送る OPTIONS リクエストに対して
        # API Gateway が自動で CORS ヘッダー付きレスポンスを返す
        x-amazon-apigateway-cors:
          allowOrigins:
            - "*"                    # プリフライトは全オリジン許可
            # (実際の API レスポンスの CORS は Lambda が ALLOWED_ORIGINS で制限)
          allowMethods:
            - GET
            - POST
            - PUT
            - DELETE
            - OPTIONS
          allowHeaders:
            - Content-Type

        # ----- ルート定義 -----
        paths:

          # ===== /todos =====
          /todos:

            # --- POST /todos (Todo 作成) ---
            post:
              x-amazon-apigateway-integration:
              # ↑ API Gateway 独自の OpenAPI 拡張。バックエンド連携の設定

                type: aws_proxy
                # ↑ Lambda プロキシ統合。リクエスト全体を Lambda にそのまま渡し、
                #   Lambda のレスポンスをそのままクライアントに返す

                httpMethod: POST
                # ↑ API Gateway → Lambda の呼び出しは常に POST
                #   (クライアント → API Gateway のメソッドとは無関係)

                uri:
                  Fn::Sub: arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${CreateTodoFunction.Arn}/invocations
                # ↑ Lambda 関数の呼び出し URI
                # Fn::Sub は文字列内の ${...} を実際の値に置換する
                #   ${AWS::Region}           → デプロイ先リージョン (ap-northeast-1)
                #   ${CreateTodoFunction.Arn} → Lambda 関数の ARN

                credentials:
                  Fn::GetAtt: [ApiGatewayInvokeRole, Arn]
                # ↑ ★★★ ここが最重要 ★★★
                # API Gateway がこのロールを AssumeRole して Lambda を呼び出す
                # これにより lambda:AddPermission (リソースベースポリシー) が不要になる
                # Fn::GetAtt で ApiGatewayInvokeRole の ARN を取得

                payloadFormatVersion: "2.0"
                # ↑ HTTP API v2 のペイロード形式。Lambda に渡される event の構造を決定
                #   1.0 = REST API 互換形式
                #   2.0 = HTTP API v2 のネイティブ形式 (よりシンプル)

            # --- GET /todos (Todo 一覧取得) ---
            get:
              x-amazon-apigateway-integration:
                type: aws_proxy
                httpMethod: POST
                uri:
                  Fn::Sub: arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${ListTodosFunction.Arn}/invocations
                credentials:
                  Fn::GetAtt: [ApiGatewayInvokeRole, Arn]
                payloadFormatVersion: "2.0"
                # (構造は POST /todos と同じ。uri の関数名だけが異なる)

          # ===== /todos/{id} =====
          # {id} はパスパラメータ。リクエスト URL の /todos/abc-123 の abc-123 が
          # Lambda の event["pathParameters"]["id"] に渡される
          /todos/{id}:

            # --- GET /todos/{id} (Todo 単体取得) ---
            get:
              x-amazon-apigateway-integration:
                type: aws_proxy
                httpMethod: POST
                uri:
                  Fn::Sub: arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${GetTodoFunction.Arn}/invocations
                credentials:
                  Fn::GetAtt: [ApiGatewayInvokeRole, Arn]
                payloadFormatVersion: "2.0"

            # --- PUT /todos/{id} (Todo 更新) ---
            put:
              x-amazon-apigateway-integration:
                type: aws_proxy
                httpMethod: POST
                uri:
                  Fn::Sub: arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${UpdateTodoFunction.Arn}/invocations
                credentials:
                  Fn::GetAtt: [ApiGatewayInvokeRole, Arn]
                payloadFormatVersion: "2.0"

            # --- DELETE /todos/{id} (Todo 削除) ---
            delete:
              x-amazon-apigateway-integration:
                type: aws_proxy
                httpMethod: POST
                uri:
                  Fn::Sub: arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${DeleteTodoFunction.Arn}/invocations
                credentials:
                  Fn::GetAtt: [ApiGatewayInvokeRole, Arn]
                payloadFormatVersion: "2.0"

  # ----- Lambda 関数 (5つ) -----
  # 注意: Events プロパティがない
  # → SAM は Lambda::Permission (リソースベースポリシー) を自動生成しない
  # → lambda:AddPermission が呼ばれない → SCP に抵触しない
  # → ルーティングは上の DefinitionBody で定義済み

  CreateTodoFunction:
    Type: AWS::Serverless::Function  # SAM の Lambda 関数リソース
    Properties:
      Handler: handlers.create_todo.handler
      # ↑ Lambda が呼び出す関数の場所
      # handlers/create_todo.py の handler() 関数

      CodeUri: src/
      # ↑ Lambda にデプロイするソースコードのディレクトリ
      # src/ 以下がまるごと Lambda にアップロードされる
      # → handlers/ と shared/ が両方含まれる

      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref TodoTable
      # ↑ SAM ポリシーテンプレート
      # TodoTable に対する CRUD (Create/Read/Update/Delete) 権限を自動生成
      # 内部的には dynamodb:GetItem, PutItem, DeleteItem, Scan 等の権限になる

  # (以下の 4 関数は構造が同じ。Handler の関数名だけが異なる)

  ListTodosFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: handlers.list_todos.handler    # GET /todos
      CodeUri: src/
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref TodoTable

  GetTodoFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: handlers.get_todo.handler      # GET /todos/{id}
      CodeUri: src/
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref TodoTable

  UpdateTodoFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: handlers.update_todo.handler   # PUT /todos/{id}
      CodeUri: src/
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref TodoTable

  DeleteTodoFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: handlers.delete_todo.handler   # DELETE /todos/{id}
      CodeUri: src/
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref TodoTable

  # ----- DynamoDB テーブル -----

  TodoTable:
    Type: AWS::DynamoDB::Table       # DynamoDB テーブルリソース
    Properties:
      TableName: todo-table-dev      # テーブル名
      BillingMode: PAY_PER_REQUEST   # オンデマンド課金 (使った分だけ)
      # PROVISIONED にするとスループット事前設定が必要。MVP ではオンデマンドが手軽

      AttributeDefinitions:
        - AttributeName: PK           # パーティションキーの属性名
          AttributeType: S            # S = String (文字列型)
      # DynamoDB ではキーに使う属性だけをここで定義する
      # title, completed 等の属性は定義不要 (スキーマレス)

      KeySchema:
        - AttributeName: PK           # PK をパーティションキーとして使用
          KeyType: HASH               # HASH = パーティションキー
      # ソートキー (RANGE) は使わない (単一キー設計)

# ===== 出力 (デプロイ完了時に表示される情報) =====

Outputs:
  ApiUrl:
    Description: API Gateway endpoint URL
    Value: !Sub "https://${TodoApi}.execute-api.${AWS::Region}.amazonaws.com/dev"
    # デプロイされた API の URL
    # ${TodoApi} → API Gateway のリソース ID (例: s5ohz97p6c)
    # ${AWS::Region} → リージョン (例: ap-northeast-1)
    # → https://s5ohz97p6c.execute-api.ap-northeast-1.amazonaws.com/dev
```

---

## 6. 参考資料

- [Control Tower CT.LAMBDA.PV.2 の詳細](https://zenn.dev/rescuenow/articles/814391b63bb83d)
- [API Gateway HTTP API の IAM 認証](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-access-control-iam.html)
- [SAM HttpApi DefinitionBody](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-resource-httpapi.html)
