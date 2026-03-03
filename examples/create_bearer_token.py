"""
Utility: Create Bearer Tokens for Testing

Generate test tokens for local development and testing.
These tokens work with North MCP servers that don't have a server_secret configured.

Usage:
    python create_bearer_token.py
    python create_bearer_token.py --email user@example.com
    python create_bearer_token.py --server-secret mysecret
    python create_bearer_token.py --connectors google,slack
"""

import argparse
import json
from base64 import b64encode

import jwt

from north_mcp_python_sdk.auth import AuthHeaderTokens


def create_bearer_token(
    email: str,
    server_secret: str | None = None,
    connectors: dict[str, str] | None = None,
) -> str:
    """Create a base64-encoded bearer token for testing."""
    user_id_token = jwt.encode(payload={"email": email}, key="test-key")

    header = AuthHeaderTokens(
        server_secret=server_secret,
        user_id_token=user_id_token,
        connector_access_tokens=connectors or {},
    )

    header_json = json.dumps(header.model_dump())
    return b64encode(header_json.encode()).decode()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create a bearer token for testing North MCP servers."
    )
    parser.add_argument(
        "--email",
        type=str,
        default="test@example.com",
        help="Email for the test user (default: test@example.com)",
    )
    parser.add_argument(
        "--server-secret",
        type=str,
        default=None,
        help="Server secret (only if server requires one)",
    )
    parser.add_argument(
        "--connectors",
        type=str,
        default=None,
        help="Comma-separated connector names (e.g., google,slack)",
    )
    args = parser.parse_args()

    connectors = None
    if args.connectors:
        connectors = {
            name: f"test-token-{name}" for name in args.connectors.split(",")
        }

    token = create_bearer_token(
        email=args.email,
        server_secret=args.server_secret,
        connectors=connectors,
    )

    print("Bearer token created:")
    print()
    print(f"  Authorization: Bearer {token}")
    print()
    print("Token contents:")
    print(f"  Email: {args.email}")
    print(f"  Server secret: {args.server_secret or '(none)'}")
    print(
        f"  Connectors: {list(connectors.keys()) if connectors else '(none)'}"
    )
