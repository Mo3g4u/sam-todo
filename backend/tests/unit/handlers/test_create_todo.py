import json

from moto import mock_aws

from handlers.create_todo import handler


class TestCreateTodoHandler:
    @mock_aws
    def test_creates_todo_and_returns_201(self, dynamo_table):
        event = {"body": json.dumps({"title": "買い物に行く"})}

        resp = handler(event, None)

        assert resp["statusCode"] == 201
        body = json.loads(resp["body"])
        assert body["title"] == "買い物に行く"
        assert body["completed"] is False
        assert "id" in body

    @mock_aws
    def test_returns_400_when_title_missing(self, dynamo_table):
        event = {"body": json.dumps({})}

        resp = handler(event, None)

        assert resp["statusCode"] == 400

    @mock_aws
    def test_returns_400_when_body_is_empty(self, dynamo_table):
        event = {"body": None}

        resp = handler(event, None)

        assert resp["statusCode"] == 400
