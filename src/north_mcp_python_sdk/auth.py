import base64
import contextvars
import logging

import jwt
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


auth_tokens_context_var = contextvars.ContextVar[AuthHeaderTokens | None](
    "north_auth_tokens_context", default=None
)

auth_context_var = contextvars.ContextVar[AuthenticatedNorthUser | None](
    "north_auth_context", default=None
)


def on_auth_error(request: HTTPConnection, exc: AuthenticationError) -> JSONResponse:
    return JSONResponse({"error": str(exc)}, status_code=401)


def get_auth_tokens() -> AuthHeaderTokens:
    """
    Get the raw authentication tokens from the current request context.
    
    Returns:
        AuthHeaderTokens: The parsed auth header containing server_secret, 
                         user_id_token, and connector_access_tokens
    
    Raises:
        Exception: If no auth tokens are found in the current context
    """
    tokens = auth_tokens_context_var.get()
    if not tokens:
        raise Exception("auth tokens not found in context")
    return tokens


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
            self.logger.debug("Authentication failed: user not found in context. User type: %s", type(user))
            raise AuthenticationError("user not found in context")

        # Get the auth tokens from the scope
        auth_tokens = scope.get("auth_tokens")
        if not isinstance(auth_tokens, AuthHeaderTokens):
            self.logger.debug("Auth tokens not found in scope")
            raise AuthenticationError("auth tokens not found in scope")

        self.logger.debug("Setting authenticated user and tokens in context: email=%s, connectors=%s", user.email, list(user.connector_access_tokens.keys()))

        user_token = auth_context_var.set(user)
        tokens_token = auth_tokens_context_var.set(auth_tokens)
        try:
            await self.app(scope, receive, send)
        finally:
            auth_context_var.reset(user_token)
            auth_tokens_context_var.reset(tokens_token)


class NorthAuthBackend(AuthenticationBackend):
    """
    Authentication backend that validates Bearer tokens.
    """

    def __init__(self, server_secret: str | None = None, debug: bool = False):
        self._server_secret = server_secret
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
            self.logger.debug("Successfully parsed auth tokens. Has server_secret: %s, Has user_id_token: %s, Connector count: %d", tokens.server_secret is not None, tokens.user_id_token is not None, len(tokens.connector_access_tokens))
            self.logger.debug("Available connectors: %s", list(tokens.connector_access_tokens.keys()))
            
            # Store tokens in scope for later access
            conn.scope["auth_tokens"] = tokens
            
        except ValidationError as e:
            self.logger.debug("Failed to validate auth tokens: %s", e)
            raise AuthenticationError("unable to decode bearer token")

        if self._server_secret and self._server_secret != tokens.server_secret:
            self.logger.debug("Server secret mismatch - access denied")
            raise AuthenticationError("access denied")

        if tokens.user_id_token:
            try:
                user_id_token = jwt.decode(
                    jwt=tokens.user_id_token,
                    verify=False,
                    options={"verify_signature": False},
                )

                email = user_id_token.get("email")
                
                self.logger.debug("Successfully decoded user ID token. Email: %s", email)

                return AuthCredentials(), AuthenticatedNorthUser(
                    connector_access_tokens=tokens.connector_access_tokens, email=email
                )
            except Exception as e:
                self.logger.debug("Failed to decode user ID token: %s", e)
                raise AuthenticationError("invalid user id token")

        self.logger.debug("Authentication successful without user ID token")

        return AuthCredentials(), AuthenticatedNorthUser(
            connector_access_tokens=tokens.connector_access_tokens,
        )
