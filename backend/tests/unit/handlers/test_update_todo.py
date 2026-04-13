import json

from moto import mock_aws

from handlers.create_todo import handler as create_handler
from handlers.update_todo import handler
from tests.conftest import make_event


class TestUpdateTodoHandler:
    @mock_aws
    def test_updates_title(self, dynamo_table):
        create_resp = create_handler(make_event(body={"title": "元のタイトル"}), None)
        todo_id = json.loads(create_resp["body"])["id"]

        resp = handler(
            make_event(body={"title": "新しいタイトル"}, path_params={"id": todo_id}),
            None,
        )

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["title"] == "新しいタイトル"

    @mock_aws
    def test_updates_completed(self, dynamo_table):
        create_resp = create_handler(make_event(body={"title": "テスト"}), None)
        todo_id = json.loads(create_resp["body"])["id"]

        resp = handler(
            make_event(body={"completed": True}, path_params={"id": todo_id}),
            None,
        )

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["completed"] is True

    @mock_aws
    def test_returns_404_when_not_found(self, dynamo_table):
        resp = handler(
            make_event(body={"title": "x"}, path_params={"id": "nonexistent"}),
            None,
        )

        assert resp["statusCode"] == 404

    @mock_aws
    def test_returns_404_for_other_users_todo(self, dynamo_table):
        create_resp = create_handler(make_event(body={"title": "他人"}, user_id="other-user"), None)
        todo_id = json.loads(create_resp["body"])["id"]

        resp = handler(
            make_event(body={"completed": True}, path_params={"id": todo_id}),
            None,
        )

        assert resp["statusCode"] == 404
