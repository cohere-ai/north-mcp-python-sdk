from north_mcp_python_sdk import NorthMCPServer
from north_mcp_python_sdk.auth import get_authenticated_user

# Create server with trusted issuer verification
# When trusted_issuers is set, the server will verify JWT signatures
# against the specified OAuth/OIDC providers
mcp = NorthMCPServer(
    "Trusted Issuers Demo", 
    port=5224,
    trusted_issuers=["https://cohere.okta.com"],
    debug=True
)


@mcp.tool()
def secure_add(a: int, b: int) -> int:
    """Add two numbers (requires verified JWT signature)"""
    
    try:
        user = get_authenticated_user()
        print(f"Secure add called by verified user: {user.email}")
    except Exception as e:
        print(f"Authentication failed: {e}")
        raise
        
    result = a + b
    print(f"Secure calculation: {a} + {b} = {result}")
    return result


@mcp.tool()
def get_verified_user_info() -> dict:
    """Get information about the JWT-verified user"""
    
    try:
        user = get_authenticated_user()
        return {
            "email": user.email,
            "available_connectors": list(user.connector_access_tokens.keys()),
            "signature_verified": True,
            "note": "This user's JWT signature was cryptographically verified"
        }
    except Exception as e:
        return {
            "error": str(e),
            "signature_verified": False
        }


if __name__ == "__main__":
    print("Starting North MCP Server with trusted issuer verification...")
    print("This server will verify JWT signatures from trusted issuers:")
    for issuer in mcp._trusted_issuers:
        print(f"  - {issuer}")
    print()
    print("Only tokens signed by these issuers will be accepted.")
    print("Server running on port 5224...")
    
    mcp.run(transport="streamable-http")
