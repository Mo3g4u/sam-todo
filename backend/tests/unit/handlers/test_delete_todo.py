import json

from moto import mock_aws

from handlers.create_todo import handler as create_handler
from handlers.delete_todo import handler
from handlers.list_todos import handler as list_handler


class TestDeleteTodoHandler:
    @mock_aws
    def test_deletes_todo_and_returns_204(self, dynamo_table):
        create_resp = create_handler({"body": json.dumps({"title": "削除するTodo"})}, None)
        todo_id = json.loads(create_resp["body"])["id"]

        resp = handler({"pathParameters": {"id": todo_id}}, None)

        assert resp["statusCode"] == 204
        list_resp = list_handler({}, None)
        assert json.loads(list_resp["body"]) == []

    @mock_aws
    def test_returns_204_even_when_not_found(self, dynamo_table):
        resp = handler({"pathParameters": {"id": "nonexistent"}}, None)

        assert resp["statusCode"] == 204
