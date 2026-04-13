#!/bin/bash
set -e

ENDPOINT="http://localhost:8000"
TABLE_NAME="todo-table-dev"
REGION="ap-northeast-1"

# DynamoDB Local requires credentials but doesn't validate them
export AWS_ACCESS_KEY_ID="dummy"
export AWS_SECRET_ACCESS_KEY="dummy"
export AWS_DEFAULT_REGION="$REGION"

# Wait for DynamoDB Local to be ready
for i in $(seq 1 10); do
  if aws dynamodb list-tables --endpoint-url "$ENDPOINT" --no-cli-pager 2>/dev/null; then
    break
  fi
  echo "Waiting for DynamoDB Local..."
  sleep 1
done

# Delete old table (schema changed from PK-only to PK+SK)
if aws dynamodb describe-table --table-name "$TABLE_NAME" --endpoint-url "$ENDPOINT" --no-cli-pager 2>/dev/null; then
  aws dynamodb delete-table --table-name "$TABLE_NAME" --endpoint-url "$ENDPOINT" --no-cli-pager 2>/dev/null
  echo "Deleted old table $TABLE_NAME"
fi

# Create table with PK + SK
aws dynamodb create-table \
  --table-name "$TABLE_NAME" \
  --attribute-definitions \
    AttributeName=PK,AttributeType=S \
    AttributeName=SK,AttributeType=S \
  --key-schema \
    AttributeName=PK,KeyType=HASH \
    AttributeName=SK,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --endpoint-url "$ENDPOINT" \
  --no-cli-pager
echo "Table $TABLE_NAME created (PK + SK)"
