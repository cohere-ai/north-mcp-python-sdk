import argparse
import logging
import os
from typing import Literal
from typing_extensions import override

from fastmcp.server.auth import AuthProvider, JWTVerifier, OAuthProxy
from mcp.server.auth.provider import AccessToken as SDKAccessToken
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_access_token

from north_mcp_python_sdk import NorthTokenVerifier, get_north_context

# ============================================================================
# Configuration (from environment)
# ============================================================================

# Configure root logger to output to console (INFO level to reduce noise)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Enable debug logging only for your modules
logging.getLogger("north").setLevel(logging.DEBUG)

DEX_ISSUER = os.getenv("DEX_ISSUER", "http://localhost:5886/dex")
DEX_JWKS_URI = os.getenv("DEX_JWKS_URI", "http://localhost:5886/dex/keys")
DEX_AUTH_ENDPOINT = os.getenv(
    "DEX_AUTH_ENDPOINT", "http://localhost:5886/dex/auth"
)
DEX_TOKEN_ENDPOINT = os.getenv(
    "DEX_TOKEN_ENDPOINT", "http://localhost:5886/dex/token"
)
CLIENT_ID = os.getenv("CLIENT_ID", "example-app")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "ZXhhbXBsZS1hcHAtc2VjcmV0")
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "http://localhost:5885")
SERVER_HOST = os.getenv("SERVER_HOST", "localhost")
SERVER_PORT = int(os.getenv("SERVER_PORT", "5885"))

# North auth configuration
NORTH_TRUSTED_ISSUERS = (
    os.getenv("NORTH_TRUSTED_ISSUERS", "").split(",")
    if os.getenv("NORTH_TRUSTED_ISSUERS")
    else None
)


# ============================================================================
# Custom OAuthProxy with Upstream Token Logging
# ============================================================================


class LoggingOAuthProxy(OAuthProxy):
    """OAuthProxy that logs the upstream token for debugging."""

    @override
    async def load_access_token(self, token: str) -> SDKAccessToken | None:
        """Override to log the upstream token."""
        try:
            # Verify FastMCP JWT signature and claims
            payload = self.jwt_issuer.verify_token(token)
            jti = payload["jti"]

            # Look up upstream token via JTI mapping
            jti_mapping = await self._jti_mapping_store.get(key=jti)
            if not jti_mapping:
                raise Exception(f"No JTI mapping found for JTI: {jti}")

            # Get the upstream token set
            upstream_token_set = await self._upstream_token_store.get(
                key=jti_mapping.upstream_token_id
            )
            if upstream_token_set:
                print(
                    f"[UPSTREAM TOKEN] access_token:\n{upstream_token_set.access_token}\n"
                )
            else:
                print(
                    f"[UPSTREAM TOKEN] No upstream token found for JTI: {jti}"
                )

        except Exception as e:
            print(f"[UPSTREAM TOKEN] Error fetching upstream token: {e}")

        # Call the parent implementation for actual validation
        return await super().load_access_token(token)


# ============================================================================
# Auth Builders
# ============================================================================


def build_jwt_verifier() -> JWTVerifier:
    """Build a JWTVerifier for token validation."""
    return JWTVerifier(
        jwks_uri=DEX_JWKS_URI,
        issuer=DEX_ISSUER,
        audience=CLIENT_ID,
    )


def build_oauth_proxy() -> OAuthProxy:
    """Build an OAuthProxy that handles the full OAuth flow."""
    return LoggingOAuthProxy(
        upstream_authorization_endpoint=DEX_AUTH_ENDPOINT,
        upstream_token_endpoint=DEX_TOKEN_ENDPOINT,
        upstream_client_id=CLIENT_ID,
        upstream_client_secret=CLIENT_SECRET,
        token_verifier=build_jwt_verifier(),
        base_url=SERVER_BASE_URL,
        redirect_path="/auth/callback",
        valid_scopes=["openid"],
    )


def build_north_verifier() -> NorthTokenVerifier:
    """Build a NorthTokenVerifier for North platform authentication."""
    return NorthTokenVerifier(
        trusted_issuers=NORTH_TRUSTED_ISSUERS,
        debug=True,
    )


def build_auth(
    auth_type: Literal["none", "jwt", "oauth-proxy", "north"] = "none",
) -> AuthProvider | None:
    """Build the auth provider based on the specified type."""
    match auth_type:
        case "none":
            return None
        case "jwt":
            return build_jwt_verifier()
        case "oauth-proxy":
            return build_oauth_proxy()
        case "north":
            return build_north_verifier()


# ============================================================================
# MCP Server Builder
# ============================================================================


def build_mcp(auth: AuthProvider | None) -> FastMCP:
    """Build and configure the MCP server with tools."""
    mcp = FastMCP("example-mcp", auth=auth)

    @mcp.tool()
    def add(a: int, b: int) -> int:
        """Add two numbers together."""
        return a + b

    @mcp.tool()
    def whoami() -> dict[str, object]:
        """Get information about the authenticated user (requires North auth)."""
        access_token = get_access_token()

        if access_token is None:
            return {"error": "No access token found"}

        return access_token.model_dump()

    @mcp.tool()
    def get_context() -> dict[str, str]:
        """Get the North context from the current request."""
        return get_north_context()

    return mcp


def build_app(mcp: FastMCP) -> Starlette:
    """Build the Starlette application with middleware."""
    mcp_app = mcp.http_app(path="/mcp")

    # CORS middleware required for browser-based clients (MCP Inspector)
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["Mcp-Session-Id"],
            allow_credentials=True,
        ),
    ]

    return Starlette(
        routes=[
            Mount("/", app=mcp_app),
        ],
        middleware=middleware,
        lifespan=mcp_app.lifespan,
    )


# ============================================================================
# CLI
# ============================================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the MCP server with configurable auth and middleware."
    )

    _ = parser.add_argument(
        "--auth",
        choices=["none", "jwt", "oauth-proxy", "north"],
        default="none",
        help="Authentication type: 'none' (no auth), 'jwt' (JWT verification only), 'oauth-proxy' (full OAuth flow with Dex), 'north' (North platform auth). Default: none",
    )

    _ = parser.add_argument(
        "--host",
        default=SERVER_HOST,
        help=f"Host to bind the server to. Default: {SERVER_HOST}",
    )

    _ = parser.add_argument(
        "--port",
        type=int,
        default=SERVER_PORT,
        help=f"Port to bind the server to. Default: {SERVER_PORT}",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    print(f"Starting MCP server with auth={args.auth}")

    auth = build_auth(args.auth)
    mcp = build_mcp(auth)
    app = build_app(mcp)

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
