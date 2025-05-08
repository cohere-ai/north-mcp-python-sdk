import json
from base64 import b64encode

import jwt

from north_mcp_python_sdk.auth import AuthHeaderTokens


def create_bearer_token():
    user_id_token = jwt.encode(
        payload={"email": "test@company.com"}, key="does-not-matter"
    )
    header = AuthHeaderTokens(
        server_secret="server_secret",
        user_id_token=user_id_token,
        connector_access_tokens={"google": "abc"},
    )
    header_as_json = json.dumps(header.model_dump())
    header_as_b64 = b64encode(header_as_json.encode()).decode()
    print(header_as_b64)


if __name__ == "__main__":
    create_bearer_token()
