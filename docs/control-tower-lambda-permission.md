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

## 5. 参考資料

- [Control Tower CT.LAMBDA.PV.2 の詳細](https://zenn.dev/rescuenow/articles/814391b63bb83d)
- [API Gateway HTTP API の IAM 認証](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-access-control-iam.html)
- [SAM HttpApi DefinitionBody](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-resource-httpapi.html)
