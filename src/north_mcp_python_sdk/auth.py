import base64
import contextvars
import json
import logging
import urllib.request
import urllib.parse

import jwt
from jwt import PyJWKClient
from pydantic import BaseModel, Field, ValidationError
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
    BaseUser,
)
from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class AuthHeaderTokens(BaseModel):
    server_secret: str | None
    user_id_token: str | None
    connector_access_tokens: dict[str, str] = Field(default_factory=dict)


class AuthenticatedNorthUser(BaseUser):
    def __init__(
        self,
        connector_access_tokens: dict[str, str],
        email: str | None = None,
    ):
        self.connector_access_tokens = connector_access_tokens
        self.email = email


auth_context_var = contextvars.ContextVar[AuthenticatedNorthUser | None](
    "north_auth_context", default=None
)


def on_auth_error(request: HTTPConnection, exc: AuthenticationError) -> JSONResponse:
    return JSONResponse({"error": str(exc)}, status_code=401)


def get_authenticated_user() -> AuthenticatedNorthUser:
    user = auth_context_var.get()
    if not user:
        raise Exception("user not found in context")

    return user


class AuthContextMiddleware:
    """
    Middleware that extracts the authenticated user from the request
    and sets it in a contextvar for easy access throughout the request lifecycle.

    This middleware should be added after the AuthenticationMiddleware in the
    middleware stack to ensure that the user is properly authenticated before
    being stored in the context.
    """

    def __init__(self, app: ASGIApp, debug: bool = False):
        self.app = app
        self.debug = debug
        self.logger = logging.getLogger("NorthMCP.AuthContext")
        if debug:
            self.logger.setLevel(logging.DEBUG)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "lifespan":
            return await self.app(scope, receive, send)

        user = scope.get("user")
        if not isinstance(user, AuthenticatedNorthUser):
            self.logger.debug(
                "Authentication failed: user not found in context. User type: %s",
                type(user),
            )
            raise AuthenticationError("user not found in context")

        self.logger.debug(
            "Setting authenticated user in context: email=%s, connectors=%s",
            user.email,
            list(user.connector_access_tokens.keys()),
        )

        token = auth_context_var.set(user)
        try:
            await self.app(scope, receive, send)
        finally:
            auth_context_var.reset(token)


class NorthAuthBackend(AuthenticationBackend):
    """
    Authentication backend that validates Bearer tokens.
    """

    def __init__(
        self,
        server_secret: str | None = None,
        trusted_issuer_urls: list[str] | None = None,
        debug: bool = False,
    ):
        self._server_secret = server_secret
        self._trusted_issuer_urls = trusted_issuer_urls
        self.debug = debug
        self.logger = logging.getLogger("NorthMCP.Auth")
        if debug:
            self.logger.setLevel(logging.DEBUG)

    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, BaseUser] | None:
        self.logger.debug("Authenticating request from %s", conn.client)
        # Log all headers in debug mode (be careful with sensitive data)
        headers_debug = {k: v for k, v in conn.headers.items()}
        self.logger.debug("Request headers: %s", headers_debug)

        auth_header = conn.headers.get("Authorization")

        if not auth_header:
            self.logger.debug("No Authorization header present")
            raise AuthenticationError("invalid authorization header")

        self.logger.debug("Authorization header present (length: %d)", len(auth_header))

        auth_header = auth_header.replace("Bearer ", "", 1)

        try:
            decoded_auth_header = base64.b64decode(auth_header).decode()
            self.logger.debug("Successfully decoded base64 auth header")
        except Exception as e:
            self.logger.debug("Failed to decode base64 auth header: %s", e)
            raise AuthenticationError("invalid authorization header")

        try:
            tokens = AuthHeaderTokens.model_validate_json(decoded_auth_header)
            self.logger.debug(
                "Successfully parsed auth tokens. Has server_secret: %s, Has user_id_token: %s, Connector count: %d",
                tokens.server_secret is not None,
                tokens.user_id_token is not None,
                len(tokens.connector_access_tokens),
            )
            self.logger.debug(
                "Available connectors: %s", list(tokens.connector_access_tokens.keys())
            )
        except ValidationError as e:
            self.logger.debug("Failed to validate auth tokens: %s", e)
            raise AuthenticationError("unable to decode bearer token")

        if self._server_secret and self._server_secret != tokens.server_secret:
            self.logger.debug("Server secret mismatch - access denied")
            raise AuthenticationError("access denied")

        if not tokens.user_id_token:
            self.logger.debug("Authentication successful without user ID token")
            return AuthCredentials(), AuthenticatedNorthUser(
                connector_access_tokens=tokens.connector_access_tokens,
            )

        try:
            decoded_token = jwt.decode(
                jwt=tokens.user_id_token,
                options={"verify_signature": False},
            )

            if self._trusted_issuer_urls:
                self._verify_token_signature(
                    raw_token=tokens.user_id_token,
                    decoded_token=decoded_token,
                )

            email = decoded_token.get("email")
            self.logger.debug("Successfully decoded user ID token. Email: %s", email)
            return AuthCredentials(), AuthenticatedNorthUser(
                connector_access_tokens=tokens.connector_access_tokens, email=email
            )
        except Exception as e:
            self.logger.debug("Failed to decode user ID token: %s", e)
            raise AuthenticationError("invalid user id token")

    def _verify_token_signature(self, raw_token: str, decoded_token: dict) -> None:
        self.logger.debug("Verifying user ID token signature against trusted issuers")
        issuer = decoded_token.get("iss")
        if not issuer:
            raise Exception("user id token issuer not found in token")

        if issuer not in self._trusted_issuer_urls:
            raise Exception("user id token issuer not trusted: %s" % issuer)

        openid_config_req = urllib.request.Request(
            url=urllib.parse.urljoin(issuer, "/.well-known/openid-configuration")
        )
        with urllib.request.urlopen(openid_config_req) as response:
            openid_config = json.load(response)

        unverified_header = jwt.get_unverified_header(jwt=raw_token)
        jwks_client = PyJWKClient(openid_config["jwks_uri"], cache_keys=True)
        kid, algorithm = unverified_header.get("kid"), unverified_header.get(
            "alg", "RS256"
        )
        if not kid:
            raise Exception("user id token header 'kid' not found")

        # This will raise an exception if the signature is invalid
        jwt.decode(
            jwt=raw_token,
            key=jwks_client.get_signing_key(kid).key,
            algorithms=[algorithm],
            issuer=self._trusted_issuer_urls,
            options={"verify_signature": True},
        )
