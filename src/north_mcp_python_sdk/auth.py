import base64
import contextvars
import json
import logging
import urllib.request

import jwt
from jwt import PyJWKClient
from pydantic import BaseModel, Field, ValidationError
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
    BaseUser,
)
from starlette.middleware.authentication import AuthenticationMiddleware
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


class NorthAuthenticationMiddleware(AuthenticationMiddleware):
    """
    North's authentication middleware for MCP servers that applies authentication
    only to MCP protocol endpoints (/mcp, /sse, /messages/*). Custom routes bypass authentication
    and are intended for operational purposes like Kubernetes health checks.

    MCP servers typically need these authenticated endpoints:
    - /mcp: JSON-RPC protocol endpoint for MCP communication
    - /sse: Server-sent events endpoint for streaming transport
    - /messages/*: SSE message posting endpoints for client-to-server communication

    Custom routes are automatically public and designed for:
    - Kubernetes liveness/readiness probes (/health, /ready)
    - Monitoring and metrics endpoints (/metrics, /status)
    - Other operational/orchestration needs

    No configuration needed - this behavior follows MCP best practices.
    """

    def __init__(
        self,
        app: ASGIApp,
        backend: AuthenticationBackend,
        on_error,
        protected_paths: list[str] | None = None,
        debug: bool = False,
    ):
        super().__init__(app, backend, on_error)
        # Default protected paths - only MCP protocol routes require auth
        self.protected_paths = protected_paths or ["/mcp", "/sse"]
        self.debug = debug
        self.logger = logging.getLogger("NorthMCP.Auth")
        if debug:
            self.logger.setLevel(logging.DEBUG)

    def _should_authenticate(self, path: str) -> bool:
        """
        Check if the given path requires authentication.
        Only MCP protocol paths (/mcp, /sse, /messages/*) require auth by default.
        """
        normalized_path = path.rstrip("/")
        for protected_path in self.protected_paths:
            # Check both with and without trailing slash
            if normalized_path == protected_path.rstrip("/"):
                return True

        # for SSE servers
        if path.startswith("/messages/"):
            return True

        return False

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "lifespan":
            return await self.app(scope, receive, send)

        path = scope.get("path", "")

        if not self._should_authenticate(path):
            self.logger.debug(
                "Path %s is a custom route (likely operational endpoint like health check), "
                "bypassing authentication as intended for k8s/orchestration use",
                path,
            )
            # For non-protected paths, create a minimal unauthenticated user
            scope["user"] = None
            scope["auth"] = AuthCredentials()
            return await self.app(scope, receive, send)

        self.logger.debug(
            "Path %s is an MCP protocol endpoint, applying authentication",
            path,
        )

        return await super().__call__(scope, receive, send)


auth_context_var = contextvars.ContextVar[AuthenticatedNorthUser | None](
    "north_auth_context", default=None
)
headers_context_var = contextvars.ContextVar[dict[str, str]](
    "north_headers_context", default={}
)


def on_auth_error(
    request: HTTPConnection, exc: AuthenticationError
) -> JSONResponse:
    return JSONResponse({"error": str(exc)}, status_code=401)


def get_authenticated_user() -> AuthenticatedNorthUser:
    user = auth_context_var.get()
    if not user:
        raise Exception("user not found in context")

    return user

def get_headers() -> dict[str, str]:
    headers = headers_context_var.get()
    if not headers:
        raise Exception("headers not found in context")

    return headers


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

        # For custom routes that don't require auth, user will be None
        if user is None:
            self.logger.debug(
                "Custom route accessed without authentication (operational endpoint)"
            )
            token = auth_context_var.set(None)
            try:
                await self.app(scope, receive, send)
            finally:
                auth_context_var.reset(token)
            return

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

        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        headers_context_var.set(headers)

        token = auth_context_var.set(user)
        try:
            await self.app(scope, receive, send)
        finally:
            auth_context_var.reset(token)

class HeadersContextMiddleware:
    """
    Middleware that sets the request headers in a contextvar for easy access
    throughout the request lifecycle.
    """

    def __init__(self, app: ASGIApp, debug: bool = False):
        self.app = app
        self.debug = debug
        self.logger = logging.getLogger("NorthMCP.HeadersContext")
        if debug:
            self.logger.setLevel(logging.DEBUG)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "lifespan":
            return await self.app(scope, receive, send)

        headers = dict(scope.get("headers", {}))
        self.logger.debug("Setting request headers in context: %s", headers)
        token = headers_context_var.set(headers)
        try:
            await self.app(scope, receive, send)
        finally:
            headers_context_var.reset(token)

class NorthAuthBackend(AuthenticationBackend):
    """
    Authentication backend that validates tokens from either:
    1. New X-North headers (preferred): X-North-ID-Token, X-North-Connector-Tokens, X-North-Server-Secret
    2. Legacy Authorization Bearer header (backwards compatibility)
    """

    def __init__(
        self,
        server_secret: str | None = None,
        trusted_issuers: list[str] | None = None,
        debug: bool = False,
    ):
        self._server_secret = server_secret
        self._trusted_issuers = trusted_issuers
        self.debug = debug
        self.logger = logging.getLogger("NorthMCP.AuthBackend")
        if debug:
            self.logger.setLevel(logging.DEBUG)

    def _has_x_north_headers(self, conn: HTTPConnection) -> bool:
        """Check if any X-North headers are present."""
        return any(
            header in conn.headers
            for header in [
                "X-North-ID-Token",
                "X-North-Connector-Tokens",
                "X-North-Server-Secret",
            ]
        )

    def _parse_connector_tokens(self, header_value: str) -> dict[str, str]:
        """Parse Base64 URL-safe encoded JSON connector tokens."""
        try:
            # Add padding if needed for Base64 decoding
            padded = header_value + "=" * (4 - len(header_value) % 4)
            decoded_json = base64.urlsafe_b64decode(padded).decode()
            tokens = json.loads(decoded_json)
            if not isinstance(tokens, dict):
                raise ValueError("Connector tokens must be a JSON object")
            return tokens
        except Exception as e:
            self.logger.debug("Failed to parse connector tokens: %s", e)
            raise AuthenticationError("invalid connector tokens format")

    def _validate_server_secret(self, provided_secret: str | None) -> None:
        """Validate server secret matches expected value."""
        if self._server_secret and self._server_secret != provided_secret:
            self.logger.debug("Server secret mismatch - access denied")
            raise AuthenticationError("access denied")

    def _process_user_id_token(self, user_id_token: str | None) -> str | None:
        """Process and validate user ID token, return email or None."""
        if not user_id_token:
            return None

        try:
            decoded_token = jwt.decode(
                jwt=user_id_token,
                verify=False,
                options={"verify_signature": False},
            )

            if self._trusted_issuers:
                self._verify_token_signature(
                    raw_token=user_id_token,
                    decoded_token=decoded_token,
                )

            email = decoded_token.get("email")
            self.logger.debug(
                "Successfully decoded user ID token. Email: %s", email
            )

            return email
        except (
            jwt.DecodeError,
            jwt.InvalidTokenError,
            ValueError,
            KeyError,
        ) as e:
            self.logger.debug("Failed to decode user ID token: %s", e)
            raise AuthenticationError("invalid user id token")

    def _create_authenticated_user(
        self, email: str | None, connector_access_tokens: dict[str, str]
    ) -> tuple[AuthCredentials, AuthenticatedNorthUser]:
        """Create authenticated user from validated tokens."""
        return AuthCredentials(), AuthenticatedNorthUser(
            connector_access_tokens=connector_access_tokens, email=email
        )

    async def _authenticate_x_north_headers(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, BaseUser]:
        """Authenticate using new X-North headers."""
        self.logger.debug("Using X-North headers for authentication")

        # Extract headers
        user_id_token = conn.headers.get("X-North-ID-Token")
        connector_tokens_header = conn.headers.get("X-North-Connector-Tokens")
        server_secret = conn.headers.get("X-North-Server-Secret")

        # Parse connector tokens (Base64 URL-safe encoded JSON)
        connector_access_tokens = {}
        if connector_tokens_header:
            connector_access_tokens = self._parse_connector_tokens(
                connector_tokens_header
            )

        self.logger.debug(
            "X-North headers parsed. Has server_secret: %s, Has user_id_token: %s, Connector count: %d",
            server_secret is not None,
            user_id_token is not None,
            len(connector_access_tokens),
        )
        self.logger.debug(
            "Available connectors: %s", list(connector_access_tokens.keys())
        )

        self._validate_server_secret(server_secret)
        email = self._process_user_id_token(user_id_token)

        self.logger.debug("X-North authentication successful")
        return self._create_authenticated_user(email, connector_access_tokens)

    async def _authenticate_legacy_bearer(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, BaseUser]:
        """Authenticate using legacy Authorization Bearer header (backwards compatibility)."""
        self.logger.debug(
            "Using legacy Authorization Bearer header for authentication"
        )

        auth_header = conn.headers.get("Authorization")

        if not auth_header:
            self.logger.debug("No Authorization header present")
            raise AuthenticationError("invalid authorization header")

        self.logger.debug(
            "Authorization header present (length: %d)", len(auth_header)
        )

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
                "Available connectors: %s",
                list(tokens.connector_access_tokens.keys()),
            )
        except ValidationError as e:
            self.logger.debug("Failed to validate auth tokens: %s", e)
            raise AuthenticationError("unable to decode bearer token")

        self._validate_server_secret(tokens.server_secret)
        email = self._process_user_id_token(tokens.user_id_token)

        self.logger.debug("Legacy authentication successful")
        return self._create_authenticated_user(
            email, tokens.connector_access_tokens
        )

    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, BaseUser] | None:
        self.logger.debug("Authenticating request from %s", conn.client)
        # Log all headers in debug mode (be careful with sensitive data)
        headers_debug = {k: v for k, v in conn.headers.items()}
        self.logger.debug("Request headers: %s", headers_debug)

        # Check for X-North headers first (preferred)
        if self._has_x_north_headers(conn):
            return await self._authenticate_x_north_headers(conn)

        # Fall back to legacy Authorization Bearer header
        return await self._authenticate_legacy_bearer(conn)

    def _verify_token_signature(
        self, raw_token: str, decoded_token: dict
    ) -> None:
        self.logger.debug(
            "Verifying user ID token signature against trusted issuers"
        )
        issuer = decoded_token.get("iss")
        if not issuer:
            raise AuthenticationError("Token missing issuer")

        if issuer not in self._trusted_issuers:
            raise AuthenticationError(f"Untrusted issuer: {issuer}")

        openid_config_req = urllib.request.Request(
            url=issuer.rstrip("/") + "/.well-known/openid-configuration"
        )
        try:
            with urllib.request.urlopen(
                openid_config_req, timeout=10
            ) as response:
                openid_config = json.load(response)
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            json.JSONDecodeError,
        ) as e:
            self.logger.error(
                f"Failed to fetch OpenID configuration from {issuer}: {e}"
            )
            raise AuthenticationError(
                f"Failed to verify token: unable to fetch issuer configuration"
            )

        unverified_header = jwt.get_unverified_header(jwt=raw_token)
        jwks_client = PyJWKClient(openid_config["jwks_uri"], cache_keys=True)
        kid, algorithm = (
            unverified_header.get("kid"),
            unverified_header.get("alg", "RS256"),
        )
        if not kid:
            raise AuthenticationError("Token missing key identifier")

        # This will raise an exception if the signature is invalid
        jwt.decode(
            jwt=raw_token,
            key=jwks_client.get_signing_key(kid).key,
            algorithms=[algorithm],
            issuer=issuer,
            options={"verify_signature": True, "verify_aud": False},
        )
