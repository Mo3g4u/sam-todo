import json

from moto import mock_aws

from handlers.create_todo import handler as create_handler
from handlers.update_todo import handler


class TestUpdateTodoHandler:
    @mock_aws
    def test_updates_title(self, dynamo_table):
        create_resp = create_handler({"body": json.dumps({"title": "元のタイトル"})}, None)
        todo_id = json.loads(create_resp["body"])["id"]

        resp = handler(
            {"pathParameters": {"id": todo_id}, "body": json.dumps({"title": "新しいタイトル"})},
            None,
        )

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["title"] == "新しいタイトル"

    @mock_aws
    def test_updates_completed(self, dynamo_table):
        create_resp = create_handler({"body": json.dumps({"title": "テスト"})}, None)
        todo_id = json.loads(create_resp["body"])["id"]

        resp = handler(
            {"pathParameters": {"id": todo_id}, "body": json.dumps({"completed": True})},
            None,
        )

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["completed"] is True

    @mock_aws
    def test_returns_404_when_not_found(self, dynamo_table):
        resp = handler(
            {"pathParameters": {"id": "nonexistent"}, "body": json.dumps({"title": "x"})},
            None,
        )

        assert resp["statusCode"] == 404
