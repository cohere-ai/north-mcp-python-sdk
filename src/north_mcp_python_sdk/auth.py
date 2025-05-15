import base64
import contextvars

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

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        user = scope.get("user")
        if not isinstance(user, AuthenticatedNorthUser):
            raise AuthenticationError("user not found in context")

        token = auth_context_var.set(user)
        try:
            await self.app(scope, receive, send)
        finally:
            auth_context_var.reset(token)


class NorthAuthBackend(AuthenticationBackend):
    """
    Authentication backend that validates Bearer tokens.
    """

    def __init__(self, server_secret: str | None = None):
        self._server_secret = server_secret

    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, BaseUser] | None:
        auth_header = conn.headers.get("Authorization")

        if not auth_header:
            raise AuthenticationError("invalid authorization header")

        auth_header = auth_header.replace("Bearer ", "", 1)

        try:
            decoded_auth_header = base64.b64decode(auth_header).decode()
        except Exception:
            raise AuthenticationError("invalid authorization header")

        try:
            tokens = AuthHeaderTokens.model_validate_json(decoded_auth_header)
        except ValidationError:
            raise AuthenticationError("unable to decode bearer token")

        if self._server_secret and self._server_secret != tokens.server_secret:
            raise AuthenticationError("access denied")

        if tokens.user_id_token:
            try:
                user_id_token = jwt.decode(
                    jwt=tokens.user_id_token,
                    verify=False,
                    options={"verify_signature": False},
                )

                email = user_id_token.get("email")

                return AuthCredentials(), AuthenticatedNorthUser(
                    connector_access_tokens=tokens.connector_access_tokens, email=email
                )
            except Exception:
                raise AuthenticationError("invalid user id token")

        return AuthCredentials(), AuthenticatedNorthUser(
            connector_access_tokens=tokens.connector_access_tokens,
        )
