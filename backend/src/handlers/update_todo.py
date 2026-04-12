import json
from datetime import datetime, timezone

from shared.dynamo_helper import get_table
from shared.response_builder import error, success


def handler(event, context):
    todo_id = event["pathParameters"]["id"]

    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return error("Invalid JSON body")

    try:
        table = get_table()

        existing = table.get_item(Key={"PK": f"TODO#{todo_id}"}).get("Item")
        if not existing:
            return error("Todo not found", status=404)

        update_expr_parts = []
        expr_names = {}
        expr_values = {}

        if "title" in body:
            update_expr_parts.append("#t = :t")
            expr_names["#t"] = "title"
            expr_values[":t"] = body["title"]

        if "completed" in body:
            update_expr_parts.append("#c = :c")
            expr_names["#c"] = "completed"
            expr_values[":c"] = body["completed"]

        if not update_expr_parts:
            return error("No fields to update")

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        update_expr_parts.append("updated_at = :u")
        expr_values[":u"] = now

        resp = table.update_item(
            Key={"PK": f"TODO#{todo_id}"},
            UpdateExpression="SET " + ", ".join(update_expr_parts),
            ExpressionAttributeNames=expr_names if expr_names else None,
            ExpressionAttributeValues=expr_values,
            ReturnValues="ALL_NEW",
        )

        item = resp["Attributes"]
        item.pop("PK", None)
        return success(item)
    except Exception as e:
        return error(str(e), status=500)
