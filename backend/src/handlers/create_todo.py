import json

from shared.auth import get_user_id
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
        user_id = get_user_id(event)
        item = create_todo_item(user_id, title)
        table = get_table()
        table.put_item(Item=item)

        item.pop("PK")
        item.pop("SK")
        return success(item, status=201)
    except Exception as e:
        return error(str(e), status=500)
