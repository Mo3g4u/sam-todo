import os

import boto3
import pytest
from moto import mock_aws

from shared import dynamo_helper

TEST_USER_ID = "test-user-00000000-0000-0000-0000-000000000000"


@pytest.fixture
def aws_env():
    os.environ["TABLE_NAME"] = "todo-table-dev"
    os.environ["AWS_DEFAULT_REGION"] = "ap-northeast-1"
    yield
    os.environ.pop("TABLE_NAME", None)


@pytest.fixture
def dynamo_table(aws_env):
    with mock_aws():
        dynamo_helper._table = None
        client = boto3.client("dynamodb", region_name="ap-northeast-1")
        client.create_table(
            TableName="todo-table-dev",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield
        dynamo_helper._table = None


def make_event(body=None, path_params=None, user_id=TEST_USER_ID):
    """テスト用の API Gateway event を生成する"""
    event = {}
    if body is not None:
        import json

        event["body"] = json.dumps(body)
    else:
        event["body"] = None
    if path_params:
        event["pathParameters"] = path_params
    event["requestContext"] = {"authorizer": {"jwt": {"claims": {"sub": user_id}}}}
    return event
