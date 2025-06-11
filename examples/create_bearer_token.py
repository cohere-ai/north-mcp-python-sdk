# This is just a test script to generate a fake token.
import argparse
import json
from base64 import b64encode

import jwt

from north_mcp_python_sdk.auth import AuthHeaderTokens


def create_bearer_token(email: str):
    user_id_token = jwt.encode(payload={"email": email}, key="does-not-matter")
    header = AuthHeaderTokens(
        server_secret="server_secret",
        user_id_token=user_id_token,
        connector_access_tokens={"google": "abc"},
    )
    header_as_json = json.dumps(header.model_dump())
    header_as_b64 = b64encode(header_as_json.encode()).decode()
    return header_as_b64


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create a bearer token to use with the MCP server."
    )
    parser.add_argument(
        "--email",
        type=str,
        default="test@company.com",
        help="Email of the user to create a token for (default: test@company.com)",
    )
    args = parser.parse_args()

    bearer_token = create_bearer_token(email=args.email)
    print(bearer_token)
