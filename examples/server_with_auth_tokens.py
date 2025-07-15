from north_mcp_python_sdk import NorthMCPServer, get_auth_tokens
from north_mcp_python_sdk.auth import get_authenticated_user

mcp = NorthMCPServer("Demo with Auth Tokens", port=5223)


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers with custom auth handling"""

    try:
        # Get the authenticated user as usual
        user = get_authenticated_user()
        print(f"This tool was called by: {user.email}")
        
        # Get the raw auth tokens for custom logic
        auth_tokens = get_auth_tokens()
        
        # Example: Use server_secret to load an API key
        if auth_tokens.server_secret:
            # In a real implementation, you might load an API key from a database
            # or external service using the server_secret
            print(f"Server secret provided: {auth_tokens.server_secret}")
            # api_key = load_api_key_from_database(auth_tokens.server_secret)
            
        # Example: Access connector tokens directly
        available_connectors = list(auth_tokens.connector_access_tokens.keys())
        print(f"Available connector tokens: {available_connectors}")
        
        # Example: Use specific connector token
        if "google" in auth_tokens.connector_access_tokens:
            google_token = auth_tokens.connector_access_tokens["google"]
            print(f"Google token available: {google_token[:10]}...")
            
        # Example: Check if user_id_token is present
        if auth_tokens.user_id_token:
            print("User ID token is present for additional validation")
        
    except Exception as e:
        print(f"Authentication error: {e}")

    return a + b


@mcp.tool()
def get_auth_info() -> dict:
    """Get detailed authentication information"""
    
    try:
        user = get_authenticated_user()
        tokens = get_auth_tokens()
        
        return {
            "user_email": user.email,
            "has_server_secret": tokens.server_secret is not None,
            "has_user_id_token": tokens.user_id_token is not None,
            "available_connectors": list(tokens.connector_access_tokens.keys()),
            "connector_count": len(tokens.connector_access_tokens)
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
