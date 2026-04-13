import pytest

from shared.auth import get_user_id


class TestGetUserId:
    def test_extracts_sub_from_jwt_claims(self):
        event = {"requestContext": {"authorizer": {"jwt": {"claims": {"sub": "user-abc-123"}}}}}

        assert get_user_id(event) == "user-abc-123"

    def test_raises_when_no_authorizer(self):
        event = {"requestContext": {}}

        with pytest.raises(KeyError):
            get_user_id(event)
