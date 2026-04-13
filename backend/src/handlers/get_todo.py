from shared.auth import get_user_id
from shared.dynamo_helper import get_table
from shared.response_builder import error, success


def handler(event, context):
    todo_id = event["pathParameters"]["id"]

    try:
        user_id = get_user_id(event)
        table = get_table()
        resp = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"TODO#{todo_id}"})
        item = resp.get("Item")

        if not item:
            return error("Todo not found", status=404)

        item.pop("PK", None)
        item.pop("SK", None)
        return success(item)
    except Exception as e:
        return error(str(e), status=500)
