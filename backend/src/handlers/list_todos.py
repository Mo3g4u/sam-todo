from shared.dynamo_helper import get_table
from shared.response_builder import error, success


def handler(event, context):
    try:
        table = get_table()
        resp = table.scan()
        items = resp.get("Items", [])

        for item in items:
            item.pop("PK", None)

        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return success(items)
    except Exception as e:
        return error(str(e), status=500)
