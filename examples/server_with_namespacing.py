"""
Example demonstrating tool namespacing to prevent tool name collisions.

This example shows how different servers can use the same tool function names
without conflicts by using namespaces.
"""

from north_mcp_python_sdk import NorthMCPServer


def create_calculator_server():
    """Create a calculator server with namespace 'basic_calculator'"""
    mcp = NorthMCPServer("Basic Calculator", port=5224, namespace=True)

    @mcp.tool()
    def add(a: int, b: int) -> int:
        """Add two numbers"""
        return a + b

    @mcp.tool()
    def multiply(a: int, b: int) -> int:
        """Multiply two numbers"""
        return a * b

    @mcp.tool()
    def calculate(expression: str) -> str:
        """Evaluate a mathematical expression"""
        try:
            # Simple evaluation - in production, use a safer parser
            result = eval(expression, {"__builtins__": {}})
            return f"{expression} = {result}"
        except Exception as e:
            return f"Error: {e}"

    return mcp


def create_slack_server():
    """Create a Slack server with namespace 'slack_dev'"""
    mcp = NorthMCPServer("Slack Dev", port=5225, namespace=True)

    @mcp.tool()
    def list_channels() -> list[dict]:
        """List all Slack channels"""
        return [
            {"id": "C1234567890", "name": "general", "members": 42},
            {"id": "C0987654321", "name": "random", "members": 28},
            {"id": "C1122334455", "name": "development", "members": 15}
        ]

    @mcp.tool()
    def send_message(channel: str, message: str) -> dict:
        """Send a message to a Slack channel"""
        return {
            "channel": channel,
            "message": message,
            "timestamp": "1234567890.123",
            "status": "sent"
        }

    @mcp.tool()
    def get_user_info(user_id: str) -> dict:
        """Get information about a Slack user"""
        return {
            "id": user_id,
            "name": "John Doe",
            "email": "john.doe@company.com",
            "status": "active"
        }

    return mcp


def create_no_namespace_server():
    """Create a server without namespacing"""
    mcp = NorthMCPServer("No Namespace Demo", port=5226, namespace=False)

    @mcp.tool()
    def add(a: int, b: int) -> int:
        """Add two numbers (no namespace)"""
        return a + b

    @mcp.tool()
    def info() -> dict:
        """Get server information"""
        return {
            "server": "No Namespace Demo",
            "namespace": "disabled",
            "tools": ["add", "info"]
        }

    return mcp


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python server_with_namespacing.py [calculator|slack|no-namespace]")
        print("This will create tools with the following names:")
        print("\nCalculator server (namespace: basic_calculator):")
        print("  - basic_calculator_add")
        print("  - basic_calculator_multiply")
        print("  - basic_calculator_calculate")
        print("\nSlack server (namespace: slack_dev):")
        print("  - slack_dev_list_channels")
        print("  - slack_dev_send_message")
        print("  - slack_dev_get_user_info")
        print("\nNo namespace server:")
        print("  - add")
        print("  - info")
        sys.exit(1)
    
    server_type = sys.argv[1]
    
    if server_type == "calculator":
        server = create_calculator_server()
        print("Starting Basic Calculator server on port 5224...")
        print("Tools will be prefixed with 'basic_calculator_'")
    elif server_type == "slack":
        server = create_slack_server()
        print("Starting Slack Dev server on port 5225...")
        print("Tools will be prefixed with 'slack_dev_'")
    elif server_type == "no-namespace":
        server = create_no_namespace_server()
        print("Starting No Namespace server on port 5226...")
        print("Tools will have no namespace prefix")
    else:
        print(f"Unknown server type: {server_type}")
        sys.exit(1)
    
    server.run(transport="streamable-http")
