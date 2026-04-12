import re
from datetime import datetime, timezone

from shared.models import create_todo_item

UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
ISO8601_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class TestCreateTodoItem:
    def test_returns_item_with_required_fields(self):
        item = create_todo_item("買い物に行く")

        assert item["title"] == "買い物に行く"
        assert item["completed"] is False
        assert UUID_PATTERN.match(item["id"])
        assert item["PK"] == f"TODO#{item['id']}"
        assert ISO8601_PATTERN.match(item["created_at"])
        assert ISO8601_PATTERN.match(item["updated_at"])

    def test_generates_unique_ids(self):
        item1 = create_todo_item("タスク1")
        item2 = create_todo_item("タスク2")

        assert item1["id"] != item2["id"]

    def test_timestamps_are_utc_now(self):
        before = datetime.now(timezone.utc).replace(microsecond=0)
        item = create_todo_item("テスト")
        after = datetime.now(timezone.utc).replace(microsecond=0)

        created = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
        assert before <= created <= after
