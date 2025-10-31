import logging
from typing import Sequence

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from .north_context import (
    DEFAULT_CONNECTOR_TOKENS_HEADER,
    DEFAULT_USER_ID_TOKEN_HEADER,
    NORTH_CONTEXT_HEADER_NAMES_SCOPE_KEY,
    NORTH_CONTEXT_SCOPE_KEY,
    NorthRequestContext,
    extract_context_from_headers,
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
        trusted_issuers: Sequence[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._user_id_token_header = user_id_token_header
        self._connector_tokens_header = connector_tokens_header
        self._logger = logging.getLogger("NorthMCP.FastMCPNorthMiddleware")
        if debug:
            self._logger.setLevel(logging.DEBUG)
        self._debug = debug
        self._trusted_issuers = (
            list(trusted_issuers) if trusted_issuers else None
        )

    async def dispatch(self, request: Request, call_next):
        logger_for_headers = self._logger if self._logger.isEnabledFor(logging.DEBUG) else None
        context, source = extract_context_from_headers(
            request.headers,
            user_id_token_header=self._user_id_token_header,
            connector_tokens_header=self._connector_tokens_header,
            trusted_issuers=self._trusted_issuers,
            logger=logger_for_headers,
        )

        if context is None:
            context = NorthRequestContext()
            source = "missing"

        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug(
                "Extracted North context via %s (user_id_token=%s, connectors=%s)",
                source,
                "present" if context.user_id_token else "missing",
                list(context.connector_tokens.keys()),
            )

        request.state.north_context = context
        request.scope[NORTH_CONTEXT_SCOPE_KEY] = context
        request.scope[NORTH_CONTEXT_HEADER_NAMES_SCOPE_KEY] = {
            "user_id_token_header": self._user_id_token_header,
            "connector_tokens_header": self._connector_tokens_header,
            "trusted_issuers": self._trusted_issuers,
        }

        token = set_north_request_context(context)
        try:
            response = await call_next(request)
        finally:
            reset_north_request_context(token)

        return response


__all__ = [
    "FastMCPNorthMiddleware",
    "NorthRequestContext",
    "get_north_request_context",
    "north_request_context_var",
]
