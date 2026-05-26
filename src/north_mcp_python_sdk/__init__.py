import logging
import os
from typing import Any

from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from .auth import NorthTokenVerifier, get_north_context
from .telemetry import (
    TelemetryConfig,
    TraceContextFormatter,
    _TELEMETRY_DISABLED,
    get_telemetry_config,
    get_tracer,
    traced_span,
)

_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def is_debug_mode() -> bool:
    """Check if debug mode should be enabled based on environment variable."""
    return os.getenv("DEBUG", "").lower() in ("true", "1", "yes", "on")


def _attach_trace_context_formatter(logger: logging.Logger) -> None:
    for handler in logger.handlers:
        if isinstance(handler.formatter, TraceContextFormatter):
            return
    handler = logging.StreamHandler()
    handler.setFormatter(TraceContextFormatter(_LOG_FORMAT))
    logger.addHandler(handler)


class NorthMCPServer(FastMCP):
    _debug: bool
    _logger: logging.Logger
    telemetry: TelemetryConfig

    def __init__(
        self,
        name: str | None = None,
        instructions: str | None = None,
        server_secret: str | None = None,
        trusted_issuers: list[str] | None = None,
        debug: bool | None = None,
        telemetry: TelemetryConfig | None = None,
        health_check: bool = True,
        **settings: Any,
    ):
        is_debug = debug if debug is not None else is_debug_mode()
        telemetry_config = (
            telemetry if telemetry is not None else _TELEMETRY_DISABLED
        )

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
        self.telemetry = telemetry_config

        if self._debug:
            logging.basicConfig(
                level=logging.DEBUG,
                format=_LOG_FORMAT,
            )
            self._logger = logging.getLogger(f"NorthMCP.{name or 'Server'}")
            self._logger.debug("Debug mode enabled for North MCP Server")
        else:
            self._logger = logging.getLogger(f"NorthMCP.{name or 'Server'}")
            self._logger.setLevel(logging.INFO)

        if self.telemetry.log_trace_context:
            _attach_trace_context_formatter(self._logger)

        if health_check:
            self._register_health_check()

    def _register_health_check(self) -> None:
        @self.custom_route("/health", methods=["GET"])
        async def health(_: Request) -> PlainTextResponse:
            return PlainTextResponse("OK")


__all__ = [
    "Depends",
    "NorthMCPServer",
    "NorthTokenVerifier",
    "TelemetryConfig",
    "TraceContextFormatter",
    "get_north_context",
    "get_telemetry_config",
    "get_tracer",
    "is_debug_mode",
    "traced_span",
]
