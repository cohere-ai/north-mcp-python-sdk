import base64
import json

import jwt

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from north_mcp_python_sdk.middleware import (
    FastMCPNorthMiddleware,
    get_north_request_context,
)
from north_mcp_python_sdk.north_context import AuthHeaderTokens


async def context_route(request):
    ctx = get_north_request_context()
    return JSONResponse(
        {
            "user_id_token": ctx.user_id_token,
            "connector_tokens": ctx.connector_tokens,
        }
    )


def create_app(**middleware_kwargs):
    app = Starlette(routes=[Route("/", context_route)])
    app.add_middleware(FastMCPNorthMiddleware, **middleware_kwargs)
    return app


def test_middleware_extracts_x_north_headers():
    app = create_app()
    client = TestClient(app)

    connector_tokens = {"google": "token123"}
    encoded_connectors = base64.urlsafe_b64encode(
        json.dumps(connector_tokens).encode()
    ).decode().rstrip("=")

    response = client.get(
        "/",
        headers={
            "X-North-ID-Token": "id-token",
            "X-North-Connector-Tokens": encoded_connectors,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["user_id_token"] == "id-token"
    assert data["connector_tokens"] == connector_tokens


def test_middleware_falls_back_to_legacy_bearer_header():
    app = create_app()
    client = TestClient(app)

    tokens = AuthHeaderTokens(
        server_secret="secret",
        user_id_token="legacy-id-token",
        connector_access_tokens={"slack": "legacy-token"},
    )
    encoded = base64.b64encode(json.dumps(tokens.model_dump()).encode()).decode()

    response = client.get("/", headers={"Authorization": f"Bearer {encoded}"})

    assert response.status_code == 200
    data = response.json()
    assert data["user_id_token"] == "legacy-id-token"
    assert data["connector_tokens"] == {"slack": "legacy-token"}


def test_middleware_returns_empty_context_when_no_headers():
    app = create_app()
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["user_id_token"] is None
    assert data["connector_tokens"] == {}


def test_middleware_rejects_untrusted_issuer():
    app = create_app(trusted_issuers=["https://trusted.example.com"])
    client = TestClient(app)

    token = jwt.encode(
        payload={
            "email": "user@example.com",
            "iss": "https://evil.example.com",
        },
        key="irrelevant",
    )

    response = client.get("/", headers={"X-North-ID-Token": token})

    assert response.status_code == 200
    data = response.json()
    assert data["user_id_token"] is None
    assert data["connector_tokens"] == {}
