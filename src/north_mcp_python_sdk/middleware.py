import base64
import binascii
import contextvars
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp


_DEFAULT_USER_ID_TOKEN_HEADER = "X-North-ID-Token"
_DEFAULT_CONNECTOR_TOKENS_HEADER = "X-North-Connector-Tokens"


@dataclass(frozen=True)
class NorthRequestContext:
    """Holds North-specific request context extracted from headers."""

    user_id_token: Optional[str] = None
    connector_tokens: Dict[str, str] = field(default_factory=dict)


north_request_context_var = contextvars.ContextVar[NorthRequestContext](
    "north_request_context",
    default=NorthRequestContext(),
)


def get_north_request_context() -> NorthRequestContext:
    """
    Retrieve the North request context for the current request.

    Returns:
        NorthRequestContext: The context extracted by FastMCPNorthMiddleware.
    """
    return north_request_context_var.get()


class FastMCPNorthMiddleware(BaseHTTPMiddleware):
    """
    Lightweight middleware that extracts North request metadata from headers.

    Unlike the full North authentication stack, this middleware never blocks
    requests. It simply captures context that can be leveraged inside FastMCP
    tools, prompts, or custom routes.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        user_id_token_header: str = _DEFAULT_USER_ID_TOKEN_HEADER,
        connector_tokens_header: str = _DEFAULT_CONNECTOR_TOKENS_HEADER,
        debug: bool = False,
    ) -> None:
        super().__init__(app)
        self._user_id_token_header = user_id_token_header
        self._connector_tokens_header = connector_tokens_header
        self._logger = logging.getLogger("NorthMCP.FastMCPNorthMiddleware")
        if debug:
            self._logger.setLevel(logging.DEBUG)
        self._debug = debug

    def _parse_connector_tokens(self, raw_header: str) -> Dict[str, str]:
        """
        Parse the connector tokens header, expected to be Base64-encoded JSON.

        Returns an empty dict when the header cannot be decoded or does not
        resolve to a JSON object of string keys and values.
        """
        if not raw_header:
            return {}

        padding = (-len(raw_header)) % 4
        padded_value = raw_header + ("=" * padding)

        try:
            decoded_bytes = base64.urlsafe_b64decode(padded_value)
            decoded_json = decoded_bytes.decode()
            parsed = json.loads(decoded_json)
            if isinstance(parsed, dict):
                return {
                    str(key): str(value)
                    for key, value in parsed.items()
                    if isinstance(key, str) and isinstance(value, str)
                }
        except (ValueError, json.JSONDecodeError, binascii.Error) as exc:
            self._logger.debug(
                "Failed to decode connector tokens header: %s", exc
            )

        return {}

    async def dispatch(self, request: Request, call_next):
        user_id_token = request.headers.get(self._user_id_token_header)
        connector_tokens_header = request.headers.get(
            self._connector_tokens_header
        )
        connector_tokens = self._parse_connector_tokens(
            connector_tokens_header or ""
        )

        if self._debug:
            self._logger.debug(
                "Extracted North context. Has user_id_token: %s, connectors: %s",
                bool(user_id_token),
                list(connector_tokens.keys()),
            )

        context = NorthRequestContext(
            user_id_token=user_id_token,
            connector_tokens=connector_tokens,
        )

        request.state.north_context = context
        token = north_request_context_var.set(context)

        try:
            response = await call_next(request)
        finally:
            north_request_context_var.reset(token)
            # Request.state lives for the lifetime of the request; no cleanup needed.

        return response


__all__ = [
    "FastMCPNorthMiddleware",
    "NorthRequestContext",
    "get_north_request_context",
    "north_request_context_var",
]
