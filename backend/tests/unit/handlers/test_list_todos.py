import json
from datetime import datetime, timezone
from unittest.mock import patch

from moto import mock_aws

from handlers.create_todo import handler as create_handler
from handlers.list_todos import handler
from tests.conftest import make_event


class TestListTodosHandler:
    @mock_aws
    def test_returns_empty_list(self, dynamo_table):
        event = make_event()

        resp = handler(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body == []

    @mock_aws
    def test_returns_all_todos_sorted_by_created_at_desc(self, dynamo_table):
        t1 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc)

        with patch("shared.models.datetime") as mock_dt:
            mock_dt.now.return_value = t1
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            create_handler(make_event(body={"title": "1番目"}), None)

            mock_dt.now.return_value = t2
            create_handler(make_event(body={"title": "2番目"}), None)

        resp = handler(make_event(), None)

        body = json.loads(resp["body"])
        assert len(body) == 2
        assert body[0]["title"] == "2番目"
        assert body[1]["title"] == "1番目"

    @mock_aws
    def test_does_not_return_other_users_todos(self, dynamo_table):
        create_handler(make_event(body={"title": "自分のTodo"}), None)
        create_handler(make_event(body={"title": "他人のTodo"}, user_id="other-user"), None)

        resp = handler(make_event(), None)

        body = json.loads(resp["body"])
        assert len(body) == 1
        assert body[0]["title"] == "自分のTodo"
