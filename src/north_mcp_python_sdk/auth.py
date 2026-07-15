import base64
import binascii
import json
import logging
from typing import Any, Callable

try:
    from typing import override
except ImportError:
    from typing_extensions import override

import urllib.error
import urllib.request
from warnings import warn

try:
    from warnings import deprecated
except ImportError:
    from typing_extensions import deprecated

from fastmcp.server.auth import AccessToken, AuthProvider
from fastmcp.server.dependencies import get_access_token, get_http_headers
import jwt
from jwt import PyJWKClient
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from pydantic import BaseModel, Field, ValidationError
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
    BaseUser,
)
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class AuthHeaderTokens(BaseModel):
    user_id_token: str | None
    connector_access_tokens: dict[str, str] = Field(default_factory=dict)


class AuthenticatedNorthUser(BaseUser):
    connector_access_tokens: dict[str, str]
    email: str | None

    def __init__(
        self,
        connector_access_tokens: dict[str, str],
        email: str | None = None,
    ):
        self.connector_access_tokens = connector_access_tokens
        self.email = email


class AuthenticatedNorthUserClaims(BaseModel):
    connector_access_tokens: dict[str, str]
    email: str | None


@deprecated("Use get_access_token to fetch authenticated user context.")
def get_authenticated_user() -> AuthenticatedNorthUser:
    access_token = get_access_token()

    if access_token is None:
        raise Exception(
            "Access token not found in context. Cannot construct AuthenticatedNorthUser."
        )

    claims = access_token.claims

    try:
        claims = AuthenticatedNorthUserClaims.model_validate(claims)
    except ValidationError as e:
        raise Exception(f"Failed to validate claims: {e}") from e

    if (
        access_token.token == ""
        and claims.email is None
        and not claims.connector_access_tokens
    ):
        raise Exception(
            "Access token not found in context. Cannot construct AuthenticatedNorthUser."
        )

    return AuthenticatedNorthUser(claims.connector_access_tokens, claims.email)


def get_north_context() -> dict[str, str]:
    """
    Get the North context from the current request.

    Returns a dictionary of context values extracted from request headers
    prefixed with `X-North-Context-*`. For example, a header
    `X-North-Context-AAA: BBB` would result in `{"AAA": "BBB"}`.

    Returns:
        dict[str, str]: A dictionary mapping context keys to their values.
    """
    headers = get_http_headers(include_all=True)

    context: dict[str, str] = {}
    prefix = "x-north-context-"

    for header_name, header_value in headers.items():
        if header_name.lower().startswith(prefix):
            key = header_name[len(prefix) :]
            context[key] = header_value

    return context


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

    protected_paths: list[str]
    debug: bool
    logger: logging.Logger

    def __init__(
        self,
        app: ASGIApp,
        backend: AuthenticationBackend,
        on_error: Callable[
            [HTTPConnection, AuthenticationError], JSONResponse
        ],
        protected_paths: list[str] | None = None,
        debug: bool | None = None,
    ):
        super().__init__(app, backend, on_error)
        # Default protected paths - only MCP protocol routes require auth
        self.protected_paths = protected_paths or ["/mcp", "/sse"]
        self.debug = debug if debug is not None else False
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

    @override
    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "lifespan":
            return await self.app(scope, receive, send)

        path = scope.get("path", "")

        if not self._should_authenticate(path):
            self.logger.debug(
                "Path %s is a custom route (likely operational endpoint like health check), "
                + "bypassing authentication as intended for k8s/orchestration use",
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


def on_auth_error(_: HTTPConnection, exc: AuthenticationError) -> JSONResponse:
    return JSONResponse({"error": str(exc)}, status_code=401)


class NorthAuthBackend(AuthenticationBackend):
    """
    Authentication backend that validates tokens from either:
    1. X-North headers: X-North-ID-Token and optional X-North-Connector-Tokens
    2. Legacy Authorization Bearer header (backwards compatibility)
    """

    _trusted_issuers: list[str] | None
    debug: bool
    logger: logging.Logger

    def __init__(
        self,
        trusted_issuers: list[str] | None = None,
        logger: logging.Logger | None = None,
        debug: bool = False,
    ):
        self._trusted_issuers = trusted_issuers
        self.debug = debug
        self.logger = logger or logging.getLogger("NorthMCP.AuthBackend")
        if debug:
            self.logger.setLevel(logging.DEBUG)
        self.logger.debug("NorthAuthBackend initialized")

    def _has_x_north_headers(self, conn: HTTPConnection) -> bool:
        """Check if any X-North headers are present."""
        return any(
            header in conn.headers and conn.headers[header].strip() != ""
            for header in [
                "X-North-ID-Token",
                "X-North-Connector-Tokens",
            ]
        )

    def _parse_connector_tokens(self, header_value: str) -> dict[str, str]:
        """Parse Base64 URL-safe encoded JSON connector tokens."""
        if not header_value:
            return {}

        # Add padding if needed for Base64 decoding (correctly handles len % 4 == 0)
        padding = (-len(header_value)) % 4
        padded = header_value + ("=" * padding)

        try:
            decoded_bytes = base64.urlsafe_b64decode(padded)
            decoded_json = decoded_bytes.decode()
            parsed = json.loads(decoded_json)
        except (ValueError, json.JSONDecodeError, binascii.Error) as e:
            self.logger.warning("Failed to parse connector tokens: %s", e)
            return {}

        if not isinstance(parsed, dict):
            self.logger.warning("Connector tokens must be a JSON object")
            return {}

        # Validate and filter to ensure string keys and values only
        tokens: dict[str, str] = {}
        for key, value in parsed.items():
            if isinstance(key, str) and isinstance(value, str):
                tokens[key] = value
            else:
                self.logger.debug(
                    "Skipping non-string connector token entry: %s=%s",
                    key,
                    value,
                )

        return tokens

    def _auth_is_configured(self) -> bool:
        return bool(self._trusted_issuers)

    def _process_user_id_token(self, user_id_token: str | None) -> str | None:
        """Process and validate user ID token, return email or None."""
        if not user_id_token:
            return None

        try:
            decoded_token: dict[str, Any] = jwt.decode(
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
        self,
        email: str | None,
        connector_access_tokens: dict[str, str],
        user_id_token: str | None,
    ) -> tuple[AuthCredentials, AuthenticatedUser]:
        """Create authenticated user from validated tokens."""
        if email is None:
            self.logger.warning(
                "Email is None, using empty AccessToken.client_id"
            )
        if user_id_token is None:
            self.logger.warning(
                "User ID token is None, using empty AccessToken.token"
            )

        claims: AuthenticatedNorthUserClaims = AuthenticatedNorthUserClaims(
            connector_access_tokens=connector_access_tokens,
            email=email,
        )

        return (
            AuthCredentials(),
            AuthenticatedUser(
                auth_info=AccessToken(
                    # FastMCP exposes auth context through AccessToken, so we currently
                    # lean on it as the carrier for North request context as well.
                    token=user_id_token or "",
                    client_id=email or "",
                    scopes=[],
                    claims=claims.model_dump(),
                ),
            ),
        )

    async def _authenticate_x_north_headers(
        self, conn: HTTPConnection, *, require_id_token: bool = True
    ) -> tuple[AuthCredentials, BaseUser]:
        """Authenticate using new X-North headers."""
        self.logger.debug("Using X-North headers for authentication")

        user_id_token = conn.headers.get("X-North-ID-Token")
        user_email_header = conn.headers.get("X-North-User-Email")

        if not user_id_token:
            self.logger.debug("No X-North-ID-Token header present")
            if require_id_token:
                raise AuthenticationError("no authentication headers present")
            token_email = None
        else:
            token_email = self._process_user_id_token(user_id_token)

        self.logger.debug("X-North authentication successful")

        # Additional Headers
        connector_tokens_header = conn.headers.get("X-North-Connector-Tokens")

        # Parse connector tokens (Base64 URL-safe encoded JSON)
        connector_access_tokens = {}
        if connector_tokens_header:
            warn(
                "X-North-Connector-Tokens is deprecated. Use custom headers instead.",
                DeprecationWarning,
            )
            connector_access_tokens = self._parse_connector_tokens(
                connector_tokens_header
            )

        email = token_email
        if token_email is None and user_email_header:
            email = user_email_header

        self.logger.debug(
            "X-North headers parsed. Has user_id_token: %s, Connector count: %d",
            user_id_token is not None and user_id_token != "",
            len(connector_access_tokens),
        )
        self.logger.debug(
            "Available connectors: %s", list(connector_access_tokens.keys())
        )

        return self._create_authenticated_user(
            email, connector_access_tokens, user_id_token
        )

    async def _authenticate_legacy_bearer(
        self, conn: HTTPConnection, *, require_id_token: bool = True
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
                "Successfully parsed auth tokens. Has user_id_token: %s, Connector count: %d",
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

        if not tokens.user_id_token:
            self.logger.debug("No user ID token present in bearer token")
            if require_id_token:
                raise AuthenticationError("no authentication headers present")
            email = None
        else:
            email = self._process_user_id_token(tokens.user_id_token)

        self.logger.debug("Legacy authentication successful")
        return self._create_authenticated_user(
            email, tokens.connector_access_tokens, tokens.user_id_token
        )

    @override
    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, BaseUser] | None:
        self.logger.debug("Authenticating request from %s", conn.client)
        # Log all headers in debug mode (be careful with sensitive data)
        headers_debug = {k: v for k, v in conn.headers.items()}
        self.logger.debug("Request headers: %s", headers_debug)

        if not self._auth_is_configured():
            if self._has_x_north_headers(conn):
                self.logger.debug(
                    "No auth configured, but X-North headers are present; parsing request context without enforcing authentication"
                )
                return await self._authenticate_x_north_headers(
                    conn, require_id_token=False
                )

            if conn.headers.get("Authorization"):
                self.logger.debug(
                    "No auth configured, but Authorization header is present; parsing legacy request context without enforcing authentication"
                )
                return await self._authenticate_legacy_bearer(
                    conn, require_id_token=False
                )

            self.logger.debug(
                "No trusted issuer configuration present and no auth headers provided; skipping authentication"
            )
            return self._create_authenticated_user(
                email=None,
                connector_access_tokens={},
                user_id_token=None,
            )

        # Check for X-North headers first (preferred)
        if self._has_x_north_headers(conn):
            return await self._authenticate_x_north_headers(conn)

        # Fall back to legacy Authorization Bearer header
        return await self._authenticate_legacy_bearer(conn)

    def _verify_token_signature(
        self, raw_token: str, decoded_token: dict[str, Any]
    ) -> None:
        issuer = decoded_token.get("iss")

        if self._trusted_issuers and issuer in self._trusted_issuers:
            self._verify_token_signature_from_issuer(
                raw_token=raw_token,
                issuer=issuer,
            )
            return

        if not issuer:
            raise AuthenticationError("Token missing issuer")
        raise AuthenticationError(f"Untrusted issuer: {issuer}")

    def _verify_token_signature_from_issuer(
        self, *, raw_token: str, issuer: str
    ) -> None:
        self.logger.debug(
            "Verifying user ID token signature against trusted issuers"
        )
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
                "Failed to verify token: unable to fetch issuer configuration"
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


class NorthTokenVerifier(AuthProvider):
    """
    FastMCP AuthProvider that verifies tokens against trusted OIDC issuers.

    This class integrates with FastMCP's authentication system by providing
    middleware that validates incoming requests. It supports both X-North
    headers and standard Authorization Bearer tokens.

    Authentication is only enforced on MCP protocol paths (/mcp, /sse,
    /messages/*). Custom routes (health checks, metrics, etc.) bypass
    authentication automatically.

    Args:
        trusted_issuers: List of OIDC issuer URLs for cryptographic token
            verification. If not provided, tokens are decoded but signatures
            are not verified.
        required_scopes: Optional list of scopes the token must contain.
        debug: Enable debug logging for authentication flow.

    Example:
        ```python
        from fastmcp import FastMCP
        from fastmcp.server.dependencies import get_access_token
        from north_mcp_python_sdk.auth import NorthTokenVerifier

        # Configure North authentication
        auth = NorthTokenVerifier(trusted_issuers=["https://auth.north.app"])

        # Create the MCP server with North auth
        mcp = FastMCP("my-mcp-server", auth=auth)

        @mcp.tool()
        def whoami() -> dict:
            \"\"\"Get the authenticated user's access token.\"\"\"
            token = get_access_token()
            return token.model_dump() if token else {"error": "No access token"}

        # Run with streamable HTTP
        if __name__ == "__main__":
            mcp.run(transport="http", host="localhost", port=8000)
        ```
    """

    trusted_issuers: list[str] | None
    debug: bool
    logger: logging.Logger
    backend: NorthAuthBackend

    def __init__(
        self,
        trusted_issuers: list[str] | None = None,
        *,
        debug: bool | None = None,
    ):
        super().__init__()
        self.trusted_issuers = trusted_issuers
        self.debug = debug if debug is not None else False
        self.logger = logging.getLogger(__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)

        self.backend = NorthAuthBackend(
            trusted_issuers=self.trusted_issuers,
            logger=self.logger,
            debug=self.debug,
        )

        self.logger.info(f"NorthTokenVerifier backend: {self.backend}")

    @override
    async def verify_token(self, token: str) -> AccessToken | None:
        self.logger.debug(
            "NorthTokenVerifier is not implemented. Token check not implemented in TokenVerifier class"
        )
        raise AuthenticationError("Could not verify token.")

    @override
    def get_middleware(self) -> list[Middleware]:
        """
        Return middleware stack for North authentication.

        Uses North's authentication middleware which:
        - Only authenticates MCP protocol paths (/mcp, /sse, /messages/*)
        - Allows custom routes (health checks, etc.) to bypass auth
        - Supports both X-North headers and legacy Bearer tokens
        """
        return [
            Middleware(
                NorthAuthenticationMiddleware,
                backend=self.backend,
                on_error=on_auth_error,
                debug=self.debug,
            ),
        ]
