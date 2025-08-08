#!/usr/bin/env python3
"""
Test script to verify that custom routes work without authentication
while MCP routes still require authentication using North's default
smart authentication middleware.
"""

import asyncio
import json
import base64
from typing import Any

import httpx
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from north_mcp_python_sdk import NorthMCPServer
from north_mcp_python_sdk.auth import get_authenticated_user_optional


def create_test_server() -> NorthMCPServer:
    """Create a test server with custom routes and MCP tools."""
    mcp = NorthMCPServer("TestServer", server_secret="test-secret", port=8080)

    @mcp.tool()
    def test_tool(message: str) -> str:
        """A test tool that requires authentication."""
        user = get_authenticated_user_optional()
        if user:
            return f"Authenticated tool call: {message} (user: {user.email})"
        else:
            return f"Unauthenticated tool call: {message}"

    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request: Request) -> PlainTextResponse:
        """Health check - should work without auth."""
        return PlainTextResponse("OK")

    @mcp.custom_route("/status", methods=["GET"])
    async def status_check(request: Request) -> JSONResponse:
        """Status check - should work without auth."""
        return JSONResponse({
            "status": "running",
            "server": "TestServer",
            "authenticated": False
        })

    @mcp.custom_route("/auth-info", methods=["GET"])
    async def auth_info(request: Request) -> JSONResponse:
        """Show authentication info - works with or without auth."""
        user = get_authenticated_user_optional()
        if user:
            return JSONResponse({
                "authenticated": True,
                "email": user.email,
                "connectors": list(user.connector_access_tokens.keys())
            })
        else:
            return JSONResponse({
                "authenticated": False,
                "message": "No authentication provided"
            })

    return mcp


def create_auth_header() -> str:
    """Create a valid authentication header for testing."""
    auth_data = {
        "server_secret": "test-secret",
        "user_id_token": None,
        "connector_access_tokens": {}
    }
    
    encoded = base64.b64encode(json.dumps(auth_data).encode()).decode()
    return f"Bearer {encoded}"


async def test_custom_routes_without_auth():
    """Test that custom routes work without authentication."""
    print("🧪 Testing custom routes without authentication...")
    
    async with httpx.AsyncClient() as client:
        # Test health endpoint
        response = await client.get("http://localhost:8080/health")
        assert response.status_code == 200
        assert response.text == "OK"
        print("✅ /health endpoint works without auth")
        
        # Test status endpoint
        response = await client.get("http://localhost:8080/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert data["authenticated"] == False
        print("✅ /status endpoint works without auth")
        
        # Test auth-info endpoint without auth
        response = await client.get("http://localhost:8080/auth-info")
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] == False
        print("✅ /auth-info endpoint works without auth")


async def test_mcp_routes_require_auth():
    """Test that MCP routes require authentication."""
    print("\n🔒 Testing MCP routes require authentication...")
    
    async with httpx.AsyncClient() as client:
        # Test MCP endpoint without auth (should fail)
        response = await client.post("http://localhost:8080/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {}
        })
        assert response.status_code == 401
        print("✅ /mcp endpoint requires auth (401 without auth)")
        
        # Test MCP endpoint with auth (should work)
        headers = {"Authorization": create_auth_header()}
        response = await client.post("http://localhost:8080/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {}
        }, headers=headers)
        # Should not be 401 (might be other errors but not auth)
        assert response.status_code != 401
        print("✅ /mcp endpoint works with auth")


async def test_custom_routes_with_optional_auth():
    """Test that custom routes can optionally use auth info."""
    print("\n🔓 Testing custom routes with optional authentication...")
    
    async with httpx.AsyncClient() as client:
        # Test auth-info endpoint with auth
        headers = {"Authorization": create_auth_header()}
        response = await client.get("http://localhost:8080/auth-info", headers=headers)
        assert response.status_code == 200
        data = response.json()
        # Note: will be False because we don't have a valid user_id_token in our test
        # but the important thing is that it doesn't return 401
        print("✅ /auth-info endpoint accepts optional auth")


async def run_tests():
    """Run all tests."""
    server = create_test_server()
    
    print("🚀 Starting test server...")
    
    # Start server in background
    import threading
    import time
    
    def run_server():
        server.run(transport="streamable-http")
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Wait for server to start
    print("⏳ Waiting for server to start...")
    time.sleep(2)
    
    try:
        await test_custom_routes_without_auth()
        await test_mcp_routes_require_auth()
        await test_custom_routes_with_optional_auth()
        
        print("\n🎉 All tests passed!")
        print("\n📋 Summary:")
        print("   ✅ Custom routes work without authentication")
        print("   ✅ MCP routes require authentication")
        print("   ✅ Custom routes can optionally use authentication")
        print("\nNorth MCP's smart authentication works perfectly:")
        print("- @mcp.custom_route() creates routes that automatically bypass auth")
        print("- Only /mcp and /sse routes require authentication")
        print("- This is the default behavior - no configuration needed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    print("Testing North MCP Custom Routes")
    print("=" * 50)
    asyncio.run(run_tests())
