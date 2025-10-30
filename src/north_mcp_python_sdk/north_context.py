import base64
import binascii
import contextvars
import json
import logging
from contextvars import Token
from dataclasses import dataclass, field
from typing import Dict, Optional


DEFAULT_USER_ID_TOKEN_HEADER = "X-North-ID-Token"
DEFAULT_CONNECTOR_TOKENS_HEADER = "X-North-Connector-Tokens"
DEFAULT_SERVER_SECRET_HEADER = "X-North-Server-Secret"

# Internal ASGI scope key used to pass the parsed request context downstream.
NORTH_CONTEXT_SCOPE_KEY = "_north_request_context"


@dataclass(frozen=True)
class NorthRequestContext:
    """Holds North-specific request context extracted from headers."""

    user_id_token: Optional[str] = None
    connector_tokens: Dict[str, str] = field(default_factory=dict)


north_request_context_var = contextvars.ContextVar[NorthRequestContext](
    "north_request_context", default=NorthRequestContext()
)


def get_north_request_context() -> NorthRequestContext:
    """
    Retrieve the North request context for the current request.

    Returns:
        NorthRequestContext: Context extracted either by authentication or middleware.
    """
    return north_request_context_var.get()


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


__all__ = [
    "DEFAULT_CONNECTOR_TOKENS_HEADER",
    "DEFAULT_SERVER_SECRET_HEADER",
    "DEFAULT_USER_ID_TOKEN_HEADER",
    "NORTH_CONTEXT_SCOPE_KEY",
    "NorthRequestContext",
    "decode_connector_tokens",
    "get_north_request_context",
    "north_request_context_var",
    "reset_north_request_context",
    "set_north_request_context",
]
