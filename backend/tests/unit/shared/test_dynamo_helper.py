import os

import boto3
import pytest
from moto import mock_aws

from shared import dynamo_helper


@pytest.fixture(autouse=True)
def _reset_singleton():
    dynamo_helper._table = None
    yield
    dynamo_helper._table = None


class TestGetTable:
    @mock_aws
    def test_returns_dynamodb_table_resource(self):
        os.environ["TABLE_NAME"] = "todo-table-dev"
        client = boto3.client("dynamodb", region_name="ap-northeast-1")
        client.create_table(
            TableName="todo-table-dev",
            KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "PK", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        table = dynamo_helper.get_table()

        assert table.table_name == "todo-table-dev"

    @mock_aws
    def test_uses_custom_endpoint_when_env_set(self):
        os.environ["TABLE_NAME"] = "todo-table-dev"
        os.environ["DYNAMODB_ENDPOINT"] = "http://localhost:8000"
        client = boto3.client("dynamodb", region_name="ap-northeast-1")
        client.create_table(
            TableName="todo-table-dev",
            KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "PK", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        table = dynamo_helper.get_table()

        assert table.table_name == "todo-table-dev"
        os.environ.pop("DYNAMODB_ENDPOINT", None)

    def test_raises_when_table_name_not_set(self):
        os.environ.pop("TABLE_NAME", None)

        with pytest.raises(KeyError):
            dynamo_helper.get_table()
