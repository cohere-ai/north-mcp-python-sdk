import logging
import os
import re
from typing import Any, Callable

from mcp.server.auth.provider import OAuthAuthorizationServerProvider
from mcp.server.fastmcp import FastMCP
from mcp.types import AnyFunction, ToolAnnotations
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware

from .auth import AuthContextMiddleware, NorthAuthBackend, on_auth_error


def is_debug_mode() -> bool:
    """Check if debug mode should be enabled based on environment variable."""
    return os.getenv('DEBUG', '').lower() in ('true', '1', 'yes', 'on')


__all__ = ["NorthMCPServer", "_normalize_namespace", "is_debug_mode"]


def _normalize_namespace(name: str) -> str:
    """Convert a server name to a valid namespace identifier.
    
    Examples:
        "Demo" -> "demo"
        "Slack Dev" -> "slack_dev"
        "My-Server" -> "my_server"
        "Calculator 2.0!" -> "calculator_2_0"
    """
    # Convert to lowercase and replace non-alphanumeric characters with underscores
    normalized = re.sub(r'[^a-zA-Z0-9]+', '_', name.lower())
    # Remove leading/trailing underscores and multiple consecutive underscores
    normalized = re.sub(r'^_+|_+$', '', normalized)
    normalized = re.sub(r'_+', '_', normalized)
    return normalized or 'server'


class NorthMCPServer(FastMCP):
    def __init__(
        self,
        name: str | None = None,
        instructions: str | None = None,
        server_secret: str | None = None,
        auth_server_provider: OAuthAuthorizationServerProvider[Any, Any, Any]
        | None = None,
        debug: bool | None = None,
        namespace: bool = True,
        **settings: Any,
    ):
        super().__init__(name, instructions, auth_server_provider, **settings)
        self._server_secret = server_secret
        
        # Set up namespacing
        self._namespace_enabled = namespace
        self._namespace_prefix = _normalize_namespace(name) if name and namespace else None
        
        # Auto-enable debug mode from environment variable if not explicitly set
        if debug is None:
            self._debug = is_debug_mode()
        else:
            self._debug = debug
        
        # Configure logging for debug mode
        if self._debug:
            logging.basicConfig(
                level=logging.DEBUG,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            self._logger = logging.getLogger(f"NorthMCP.{name or 'Server'}")
            self._logger.debug("Debug mode enabled for North MCP Server")
        else:
            self._logger = logging.getLogger(f"NorthMCP.{name or 'Server'}")
            self._logger.setLevel(logging.INFO)

    def _get_namespaced_tool_name(self, name: str) -> str:
        """Get the namespaced tool name if namespacing is enabled."""
        if self._namespace_enabled and self._namespace_prefix:
            return f"{self._namespace_prefix}_{name}"
        return name

    def add_tool(
        self,
        fn: AnyFunction,
        name: str | None = None,
        description: str | None = None,
        annotations: ToolAnnotations | None = None,
    ) -> None:
        """Add a tool to the server with optional namespacing.

        If namespacing is enabled, the tool name will be prefixed with the server namespace.

        Args:
            fn: The function to register as a tool
            name: Optional name for the tool (defaults to function name)
            description: Optional description of what the tool does
            annotations: Optional ToolAnnotations providing additional tool information
        """
        tool_name = name or fn.__name__
        namespaced_name = self._get_namespaced_tool_name(tool_name)
        super().add_tool(fn, name=namespaced_name, description=description, annotations=annotations)

    def tool(
        self,
        name: str | None = None,
        description: str | None = None,
        annotations: ToolAnnotations | None = None,
    ) -> Callable[[AnyFunction], AnyFunction]:
        """Decorator to register a tool with optional namespacing.

        If namespacing is enabled, the tool name will be prefixed with the server namespace.

        Args:
            name: Optional name for the tool (defaults to function name)
            description: Optional description of what the tool does
            annotations: Optional ToolAnnotations providing additional tool information

        Example:
            # With namespace "demo", this creates tool "demo/add"
            @server.tool()
            def add(x: int, y: int) -> int:
                return x + y

            # With namespace "demo", this creates tool "demo/custom_name"
            @server.tool(name="custom_name")
            def my_func() -> str:
                return "hello"
        """
        # Check if user passed function directly instead of calling decorator
        if callable(name):
            raise TypeError(
                "The @tool decorator was used incorrectly. "
                "Did you forget to call it? Use @tool() instead of @tool"
            )

        def decorator(fn: AnyFunction) -> AnyFunction:
            self.add_tool(fn, name=name, description=description, annotations=annotations)
            return fn

        return decorator

    def sse_app(self, mount_path: str | None = None) -> Starlette:
        app = super().sse_app(mount_path=mount_path)
        self._add_middleware(app)
        return app

    def streamable_http_app(self) -> Starlette:
        app = super().streamable_http_app()
        self._add_middleware(app)
        return app

    def _add_middleware(self, app: Starlette) -> None:
        middleware = [
            Middleware(
                AuthenticationMiddleware,
                backend=NorthAuthBackend(self._server_secret, debug=self._debug),
                on_error=on_auth_error,
            ),
            Middleware(AuthContextMiddleware, debug=self._debug),
        ]
        app.user_middleware.extend(middleware)
