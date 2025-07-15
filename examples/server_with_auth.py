from north_mcp_python_sdk import NorthMCPServer, get_auth_tokens
from north_mcp_python_sdk.auth import get_authenticated_user

mcp = NorthMCPServer("Demo", port=5222)


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""

    try:
        user = get_authenticated_user()
        print(f"This tool was called by: {user.email}")
        
        # Access raw auth tokens for custom logic
        auth_tokens = get_auth_tokens()
        if auth_tokens.server_secret:
            print(f"Server secret provided: {auth_tokens.server_secret}")
            # Could use server_secret to load API key from database
            
        print(f"Available connectors: {list(auth_tokens.connector_access_tokens.keys())}")
        
    except Exception:
        print("unauthenticated user")

    return a + b


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
