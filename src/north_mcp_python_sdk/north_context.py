import base64
import binascii
import contextvars
import json
import logging
from contextvars import Token
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Sequence

from pydantic import BaseModel, Field, ValidationError

from .token_utils import (
    TokenVerificationError,
    decode_user_id_token,
    verify_user_id_token,
)

try:  # FastMCP optional dependency
    from mcp.server.lowlevel import server as lowlevel_server
    from mcp.server.fastmcp.tools.base import Tool as _FastMCPTool
except ModuleNotFoundError:  # pragma: no cover
    lowlevel_server = None  # type: ignore[assignment]
    _FastMCPTool = None  # type: ignore[assignment]


DEFAULT_USER_ID_TOKEN_HEADER = "X-North-ID-Token"
DEFAULT_CONNECTOR_TOKENS_HEADER = "X-North-Connector-Tokens"
DEFAULT_SERVER_SECRET_HEADER = "X-North-Server-Secret"

# Internal ASGI scope key used to pass the parsed request context downstream.
NORTH_CONTEXT_SCOPE_KEY = "_north_request_context"
NORTH_CONTEXT_HEADER_NAMES_SCOPE_KEY = "_north_context_header_names"

LOGGER = logging.getLogger("NorthMCP.FastMCPNorthMiddleware")


@dataclass(frozen=True)
class NorthRequestContext:
    """Holds North-specific request context extracted from headers."""

    user_id_token: Optional[str] = None
    connector_tokens: Dict[str, str] = field(default_factory=dict)
    user_claims: Dict[str, Any] | None = field(
        default=None, compare=False, repr=False
    )


north_request_context_var = contextvars.ContextVar[NorthRequestContext](
    "north_request_context", default=NorthRequestContext()
)


def get_north_request_context() -> NorthRequestContext:
    """
    Retrieve the North request context for the current request.

    Returns:
        NorthRequestContext: Context extracted either by authentication or middleware.
    """
    context = north_request_context_var.get()

    if context.user_id_token or context.connector_tokens:
        return context

    if lowlevel_server is not None:
        try:
            request_context = lowlevel_server.request_ctx.get()
        except LookupError:
            request_context = None

        if request_context and request_context.request is not None:
            extracted = _extract_context_from_request(
                request_context.request, logger=LOGGER
            )
            if extracted is not None:
                return extracted

    return context


def set_north_request_context(
    context: NorthRequestContext,
) -> Token[NorthRequestContext]:
    """Set the current North request context and return the contextvar token."""
    return north_request_context_var.set(context)


def reset_north_request_context(token: Token[NorthRequestContext]) -> None:
    """Reset the North request context to its previous value."""
    north_request_context_var.reset(token)


def decode_connector_tokens(
    raw_header: str,
    *,
    logger: logging.Logger | None = None,
    raise_on_error: bool = False,
) -> Dict[str, str]:
    """
    Decode a Base64 URL-safe encoded JSON mapping of connector tokens.

    Returns an empty dict when the header is missing or invalid unless
    raise_on_error is True, in which case a ValueError is raised.
    """
    if not raw_header:
        return {}

    padding = (-len(raw_header)) % 4
    padded_value = raw_header + ("=" * padding)

    try:
        decoded_bytes = base64.urlsafe_b64decode(padded_value)
        decoded_json = decoded_bytes.decode()
        parsed = json.loads(decoded_json)
    except (ValueError, json.JSONDecodeError, binascii.Error) as exc:
        if logger:
            logger.debug("Failed to decode connector tokens header: %s", exc)
        if raise_on_error:
            raise ValueError("invalid connector tokens format") from exc
        return {}

    if not isinstance(parsed, dict):
        if raise_on_error:
            raise ValueError("connector tokens payload must be a JSON object")
        return {}

    tokens: Dict[str, str] = {}
    for key, value in parsed.items():
        if isinstance(key, str) and isinstance(value, str):
            tokens[key] = value
        elif raise_on_error:
            raise ValueError(
                "connector tokens must contain string keys and values"
            )

    return tokens

@dataclass(frozen=True)
class NorthUser:
    """Convenient view over a North identity token."""

    raw_token: Optional[str]
    claims: Mapping[str, Any]
    email: Optional[str] = None
    name: Optional[str] = None
    connector_id: Optional[str] = None
    connector_user_id: Optional[str] = None

    @classmethod
    def from_claims(
        cls, raw_token: Optional[str], claims: Mapping[str, Any]
    ) -> "NorthUser":
        email = claims.get("email")
        name = claims.get("name")
        connector_id = None
        connector_user_id = None

        federated_claims = claims.get("federated_claims")
        if isinstance(federated_claims, Mapping):
            connector_id_value = federated_claims.get("connector_id")
            if isinstance(connector_id_value, str):
                connector_id = connector_id_value

            connector_user_id_value = federated_claims.get("user_id")
            if isinstance(connector_user_id_value, str):
                connector_user_id = connector_user_id_value

        return cls(
            raw_token=raw_token,
            claims=claims,
            email=email if isinstance(email, str) else None,
            name=name if isinstance(name, str) else None,
            connector_id=connector_id,
            connector_user_id=connector_user_id,
        )


def get_north_user(default: NorthUser | None = None) -> NorthUser | None:
    """
    Convenience helper that returns a parsed representation of the current user.

    Falls back to ``default`` (None by default) when there is no active request
    or the identity token cannot be decoded.
    """
    context = get_north_request_context()
    token = context.user_id_token
    if not token:
        return default

    claims = context.user_claims
    if claims is None:
        claims = decode_user_id_token(token, logger=LOGGER)

    if claims is None:
        return default

    return NorthUser.from_claims(token, claims)


def _store_context_on_request(request: object, context: NorthRequestContext) -> None:
    """Persist the extracted context on the request object for downstream use."""
    state = getattr(request, "state", None)
    if state is not None:
        try:
            setattr(state, "north_context", context)
        except Exception:  # noqa: BLE001 - defensive programming for unexpected states
            pass

    scope = getattr(request, "scope", None)
    if isinstance(scope, dict):
        scope[NORTH_CONTEXT_SCOPE_KEY] = context


def _get_header_value(headers: Any, name: str) -> str | None:
    """
    Retrieve a header value from Starlette headers, mappings, or raw ASGI header lists.
    """
    if headers is None:
        return None

    normalized = name.lower()

    getter = getattr(headers, "get", None)
    if callable(getter):
        try:
            value = getter(name)
            if value is not None:
                return value
        except Exception:  # noqa: BLE001 - tolerate quirky header containers
            pass
        try:
            value = getter(normalized)
            if value is not None:
                return value
        except Exception:  # noqa: BLE001 - tolerate quirky header containers
            pass

    if isinstance(headers, Mapping):
        for key, value in headers.items():
            if isinstance(key, str) and key.lower() == normalized:
                return value

    if isinstance(headers, Sequence):
        target = normalized.encode("latin1")
        for item in headers:
            if not isinstance(item, Sequence) or len(item) != 2:
                continue
            raw_name, raw_value = item
            if isinstance(raw_name, bytes):
                if raw_name.lower() != target:
                    continue
                if isinstance(raw_value, bytes):
                    return raw_value.decode("latin1")
                return str(raw_value)
            if isinstance(raw_name, str) and raw_name.lower() == normalized:
                if isinstance(raw_value, bytes):
                    return raw_value.decode("latin1")
                return str(raw_value)

    return None


def extract_context_from_headers(
    headers: Any,
    *,
    user_id_token_header: str = DEFAULT_USER_ID_TOKEN_HEADER,
    connector_tokens_header: str = DEFAULT_CONNECTOR_TOKENS_HEADER,
    trusted_issuers: Sequence[str] | None = None,
    logger: logging.Logger | None = None,
) -> tuple[NorthRequestContext | None, str]:
    """
    Create a North request context from HTTP headers.

    Returns a tuple of (context, source) where context is None when nothing could be
    extracted and source describes where the data originated.
    """
    user_id_token = _get_header_value(headers, user_id_token_header)
    raw_connector_tokens = _get_header_value(headers, connector_tokens_header) or ""
    connector_tokens = decode_connector_tokens(
        raw_connector_tokens, logger=logger, raise_on_error=False
    )

    claims = None
    source = "north_headers"

    if user_id_token:
        if trusted_issuers:
            try:
                verified_claims = verify_user_id_token(
                    user_id_token, trusted_issuers, logger=logger
                )
                claims = dict(verified_claims)
                source = "north_headers_verified"
            except TokenVerificationError as exc:
                if logger:
                    logger.warning(
                        "Failed to verify user ID token from trusted issuer list: %s",
                        exc,
                    )
                user_id_token = None
                claims = None
                source = "north_headers_invalid"
        else:
            claims = decode_user_id_token(user_id_token, logger=logger)

    if user_id_token or connector_tokens:
        return (
            NorthRequestContext(
                user_id_token=user_id_token,
                connector_tokens=connector_tokens,
                user_claims=claims,
            ),
            source,
        )

    authorization_header = _get_header_value(headers, "Authorization") or ""
    bearer_tokens = parse_legacy_bearer_header(
        authorization_header, logger=logger, raise_on_error=False
    )
    if bearer_tokens:
        context = north_context_from_auth_tokens(
            bearer_tokens,
            trusted_issuers=trusted_issuers,
            logger=logger,
        )
        return context, "legacy_authorization"

    return (None, "missing")


def _extract_context_from_request(
    request: object,
    *,
    logger: logging.Logger | None = None,
) -> NorthRequestContext | None:
    state = getattr(request, "state", None)
    if state is not None:
        state_context = getattr(state, "north_context", None)
        if isinstance(state_context, NorthRequestContext):
            return state_context

    header_config: Mapping[str, Any] = {}
    scope = getattr(request, "scope", None)
    if isinstance(scope, dict):
        scope_context = scope.get(NORTH_CONTEXT_SCOPE_KEY)
        if isinstance(scope_context, NorthRequestContext):
            return scope_context
        raw_config = scope.get(NORTH_CONTEXT_HEADER_NAMES_SCOPE_KEY)
        if isinstance(raw_config, Mapping):
            header_config = raw_config

    user_header = header_config.get("user_id_token_header", DEFAULT_USER_ID_TOKEN_HEADER)
    connector_header = header_config.get(
        "connector_tokens_header", DEFAULT_CONNECTOR_TOKENS_HEADER
    )
    trusted_issuers_config = header_config.get("trusted_issuers")
    trusted_issuers_seq: Sequence[str] | None
    if isinstance(trusted_issuers_config, Sequence) and not isinstance(
        trusted_issuers_config, (str, bytes)
    ):
        trusted_issuers_seq = [str(value) for value in trusted_issuers_config]
    else:
        trusted_issuers_seq = None

    headers = getattr(request, "headers", None)
    context, source = extract_context_from_headers(
        headers,
        user_id_token_header=user_header,
        connector_tokens_header=connector_header,
        trusted_issuers=trusted_issuers_seq,
        logger=logger,
    )

    if context is None:
        return None

    _store_context_on_request(request, context)

    if logger and logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "Extracted North context from %s (user_id_token=%s, connectors=%s)",
            source,
            "present" if context.user_id_token else "missing",
            list(context.connector_tokens.keys()),
        )

    return context


class AuthHeaderTokens(BaseModel):
    server_secret: str | None
    user_id_token: str | None
    connector_access_tokens: Dict[str, str] = Field(default_factory=dict)


def parse_legacy_bearer_header(
    raw_header: str,
    *,
    logger: logging.Logger | None = None,
    raise_on_error: bool = False,
) -> AuthHeaderTokens | None:
    """
    Decode a legacy Authorization Bearer header containing North auth payload.

    Returns None when the header is missing or invalid unless raise_on_error is True,
    in which case a ValueError is raised with a message appropriate for client errors.
    """
    if not raw_header:
        return None

    token_str = raw_header.replace("Bearer ", "", 1)

    try:
        decoded = base64.b64decode(token_str).decode()
    except Exception as exc:  # noqa: BLE001 - need broad catch for decoding issues
        if logger:
            logger.debug("Failed to decode base64 auth header: %s", exc)
        if raise_on_error:
            raise ValueError("invalid authorization header") from exc
        return None

    try:
        return AuthHeaderTokens.model_validate_json(decoded)
    except ValidationError as exc:
        if logger:
            logger.debug("Failed to validate auth tokens: %s", exc)
        if raise_on_error:
            raise ValueError("unable to decode bearer token") from exc
        return None


def north_context_from_auth_tokens(
    tokens: AuthHeaderTokens | None,
    *,
    trusted_issuers: Sequence[str] | None = None,
    logger: logging.Logger | None = None,
) -> NorthRequestContext:
    """Convert parsed auth tokens into a NorthRequestContext."""
    if not tokens:
        return NorthRequestContext()

    user_id_token = tokens.user_id_token
    claims = None
    if tokens.user_id_token:
        if trusted_issuers:
            try:
                claims = dict(
                    verify_user_id_token(
                        user_id_token,
                        trusted_issuers,
                        logger=logger,
                    )
                )
            except TokenVerificationError as exc:
                if logger:
                    logger.warning(
                        "Failed to verify user ID token from auth tokens: %s",
                        exc,
                    )
                user_id_token = None
        if claims is None and user_id_token:
            claims = decode_user_id_token(user_id_token, logger=logger)

    return NorthRequestContext(
        user_id_token=user_id_token,
        connector_tokens=tokens.connector_access_tokens,
        user_claims=claims,
    )


if _FastMCPTool is not None:  # pragma: no cover - runtime patch
    _original_tool_run = _FastMCPTool.run

    async def _north_tool_run(self, arguments, context=None, convert_result=False):
        token: Token[NorthRequestContext] | None = None

        if context is not None:
            request_context = getattr(context, "request_context", None)
            request_obj = getattr(request_context, "request", None)
            extracted = _extract_context_from_request(
                request_obj, logger=LOGGER
            )
            if extracted is not None:
                token = north_request_context_var.set(extracted)
            else:
                LOGGER.debug(
                    "FastMCP tool request context missing north context. request type=%s state=%s",
                    type(request_obj),
                    getattr(getattr(request_obj, "state", None), "__dict__", None),
                )

        try:
            return await _original_tool_run(
                self, arguments, context=context, convert_result=convert_result
            )
        finally:
            if token is not None:
                north_request_context_var.reset(token)

    _FastMCPTool.run = _north_tool_run  # type: ignore[assignment]


__all__ = [
    "DEFAULT_CONNECTOR_TOKENS_HEADER",
    "DEFAULT_SERVER_SECRET_HEADER",
    "DEFAULT_USER_ID_TOKEN_HEADER",
    "NORTH_CONTEXT_SCOPE_KEY",
    "NorthRequestContext",
    "AuthHeaderTokens",
    "decode_connector_tokens",
    "decode_user_id_token",
    "verify_user_id_token",
    "TokenVerificationError",
    "get_north_request_context",
    "north_request_context_var",
    "north_context_from_auth_tokens",
    "NorthUser",
    "get_north_user",
    "extract_context_from_headers",
    "parse_legacy_bearer_header",
    "reset_north_request_context",
    "set_north_request_context",
    "NORTH_CONTEXT_HEADER_NAMES_SCOPE_KEY",
]
