import json

from moto import mock_aws

from handlers.create_todo import handler as create_handler
from handlers.list_todos import handler


class TestListTodosHandler:
    @mock_aws
    def test_returns_empty_list(self, dynamo_table):
        resp = handler({}, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body == []

    @mock_aws
    def test_returns_all_todos_sorted_by_created_at_desc(self, dynamo_table):
        create_handler({"body": json.dumps({"title": "1番目"})}, None)
        create_handler({"body": json.dumps({"title": "2番目"})}, None)

        resp = handler({}, None)

        body = json.loads(resp["body"])
        assert len(body) == 2
        assert body[0]["title"] == "2番目"
        assert body[1]["title"] == "1番目"
