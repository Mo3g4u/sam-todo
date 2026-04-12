import json

from moto import mock_aws

from handlers.create_todo import handler as create_handler
from handlers.get_todo import handler


class TestGetTodoHandler:
    @mock_aws
    def test_returns_todo_by_id(self, dynamo_table):
        create_resp = create_handler({"body": json.dumps({"title": "テスト"})}, None)
        todo_id = json.loads(create_resp["body"])["id"]

        resp = handler({"pathParameters": {"id": todo_id}}, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["title"] == "テスト"

    @mock_aws
    def test_returns_404_when_not_found(self, dynamo_table):
        resp = handler({"pathParameters": {"id": "nonexistent"}}, None)

        assert resp["statusCode"] == 404
