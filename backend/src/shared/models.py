import uuid
from datetime import datetime, timezone


def create_todo_item(title: str) -> dict:
    todo_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "PK": f"TODO#{todo_id}",
        "id": todo_id,
        "title": title,
        "completed": False,
        "created_at": now,
        "updated_at": now,
    }
