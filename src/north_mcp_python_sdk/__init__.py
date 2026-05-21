import logging
import os
from typing import Any

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from .auth import NorthTokenVerifier, get_north_context
from .telemetry import TraceContextFormatter, get_tracer, traced_span

_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def is_debug_mode() -> bool:
    """Check if debug mode should be enabled based on environment variable."""
    return os.getenv("DEBUG", "").lower() in ("true", "1", "yes", "on")


def is_verbose_mode() -> bool:
    """Check if verbose telemetry is enabled based on environment variable."""
    return os.getenv("VERBOSE", "").lower() in ("true", "1", "yes", "on")


def _attach_trace_context_formatter(logger: logging.Logger) -> None:
    for handler in logger.handlers:
        if isinstance(handler.formatter, TraceContextFormatter):
            return
    handler = logging.StreamHandler()
    handler.setFormatter(TraceContextFormatter(_LOG_FORMAT))
    logger.addHandler(handler)


class NorthMCPServer(FastMCP):
    _debug: bool
    _verbose: bool
    _logger: logging.Logger

    def __init__(
        self,
        name: str | None = None,
        instructions: str | None = None,
        server_secret: str | None = None,
        trusted_issuers: list[str] | None = None,
        debug: bool | None = None,
        verbose: bool | None = None,
        health_check: bool = True,
        **settings: Any,
    ):
        is_debug = debug if debug is not None else is_debug_mode()
        is_verbose = verbose if verbose is not None else is_verbose_mode()

        kwargs: dict[str, Any] = {
            **settings,
            "auth": NorthTokenVerifier(
                server_secret=server_secret,
                trusted_issuers=trusted_issuers,
                debug=is_debug,
            ),
        }

        super().__init__(
            name=name,
            instructions=instructions,
            **kwargs,
        )

        self._debug = is_debug
        self._verbose = is_verbose

        # Configure logging for debug mode
        if self._debug:
            logging.basicConfig(
                level=logging.DEBUG,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            )
            self._logger = logging.getLogger(f"NorthMCP.{name or 'Server'}")
            self._logger.debug("Debug mode enabled for North MCP Server")
        else:
            self._logger = logging.getLogger(f"NorthMCP.{name or 'Server'}")
            self._logger.setLevel(logging.INFO)

        _attach_trace_context_formatter(self._logger)

        if health_check:
            self._register_health_check()

    def _register_health_check(self) -> None:
        @self.custom_route("/health", methods=["GET"])
        async def health(_: Request) -> PlainTextResponse:
            return PlainTextResponse("OK")


# Convenience exports
__all__ = [
    "NorthMCPServer",
    "NorthTokenVerifier",
    "TraceContextFormatter",
    "get_north_context",
    "get_tracer",
    "is_debug_mode",
    "is_verbose_mode",
    "traced_span",
]
