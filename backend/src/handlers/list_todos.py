from boto3.dynamodb.conditions import Key

from shared.auth import get_user_id
from shared.dynamo_helper import get_table
from shared.response_builder import error, success


def handler(event, context):
    try:
        user_id = get_user_id(event)
        table = get_table()
        resp = table.query(KeyConditionExpression=Key("PK").eq(f"USER#{user_id}"))
        items = resp.get("Items", [])

        for item in items:
            item.pop("PK", None)
            item.pop("SK", None)

        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return success(items)
    except Exception as e:
        return error(str(e), status=500)
