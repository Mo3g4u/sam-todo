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
