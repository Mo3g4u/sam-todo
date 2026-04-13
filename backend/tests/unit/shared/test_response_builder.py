import json
import os
from decimal import Decimal

from shared.response_builder import error, success


class TestSuccess:
    def test_returns_200_by_default(self):
        resp = success({"message": "ok"})

        assert resp["statusCode"] == 200
        assert json.loads(resp["body"]) == {"message": "ok"}

    def test_returns_custom_status(self):
        resp = success({"id": "123"}, status=201)

        assert resp["statusCode"] == 201

    def test_handles_decimal_values(self):
        resp = success({"price": Decimal("19.99")})

        body = json.loads(resp["body"])
        assert body["price"] == 19.99

    def test_includes_content_type_header(self):
        resp = success({"ok": True})

        assert resp["headers"]["Content-Type"] == "application/json"

    def test_includes_cors_headers(self):
        resp = success({"ok": True})

        assert "Access-Control-Allow-Origin" in resp["headers"]
        assert "Access-Control-Allow-Methods" in resp["headers"]

    def test_uses_allowed_origins_env(self):
        os.environ["ALLOWED_ORIGINS"] = "https://example.com"
        resp = success({"ok": True})
        os.environ.pop("ALLOWED_ORIGINS")

        assert resp["headers"]["Access-Control-Allow-Origin"] == "https://example.com"


class TestError:
    def test_returns_400_by_default(self):
        resp = error("Bad request")

        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["error"] == "Bad request"

    def test_returns_custom_status(self):
        resp = error("Not found", status=404)

        assert resp["statusCode"] == 404

    def test_includes_cors_headers(self):
        resp = error("Bad request")

        assert "Access-Control-Allow-Origin" in resp["headers"]
