import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from .north_context import (
    DEFAULT_CONNECTOR_TOKENS_HEADER,
    DEFAULT_USER_ID_TOKEN_HEADER,
    NorthRequestContext,
    decode_connector_tokens,
    get_north_request_context,
    north_request_context_var,
    reset_north_request_context,
    set_north_request_context,
)


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
        user_id_token_header: str = DEFAULT_USER_ID_TOKEN_HEADER,
        connector_tokens_header: str = DEFAULT_CONNECTOR_TOKENS_HEADER,
        debug: bool = False,
    ) -> None:
        super().__init__(app)
        self._user_id_token_header = user_id_token_header
        self._connector_tokens_header = connector_tokens_header
        self._logger = logging.getLogger("NorthMCP.FastMCPNorthMiddleware")
        if debug:
            self._logger.setLevel(logging.DEBUG)
        self._debug = debug

    async def dispatch(self, request: Request, call_next):
        user_id_token = request.headers.get(self._user_id_token_header)
        connector_tokens_header = request.headers.get(
            self._connector_tokens_header
        )
        connector_tokens = decode_connector_tokens(
            connector_tokens_header or "", logger=self._logger
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
        token = set_north_request_context(context)

        try:
            response = await call_next(request)
        finally:
            reset_north_request_context(token)
            # Request.state lives for the lifetime of the request; no cleanup needed.

        return response


__all__ = [
    "FastMCPNorthMiddleware",
    "NorthRequestContext",
    "get_north_request_context",
    "north_request_context_var",
]
