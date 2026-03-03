import logging
import os
from typing import Any

from fastmcp import FastMCP

from .auth import NorthTokenVerifier, get_north_context


def is_debug_mode() -> bool:
    """Check if debug mode should be enabled based on environment variable."""
    return os.getenv("DEBUG", "").lower() in ("true", "1", "yes", "on")


class NorthMCPServer(FastMCP):
    _debug: bool
    _logger: logging.Logger

    def __init__(
        self,
        name: str | None = None,
        instructions: str | None = None,
        server_secret: str | None = None,
        trusted_issuers: list[str] | None = None,
        debug: bool | None = None,
        **settings: Any,
    ):
        is_debug = debug if debug is not None else is_debug_mode()

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


# Convenience exports
__all__ = [
    "NorthMCPServer",
    "NorthTokenVerifier",
    "is_debug_mode",
    "get_north_context",
]
