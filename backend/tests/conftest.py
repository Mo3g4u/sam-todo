import os

import boto3
import pytest
from moto import mock_aws

from shared import dynamo_helper


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
            KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "PK", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield
        dynamo_helper._table = None
