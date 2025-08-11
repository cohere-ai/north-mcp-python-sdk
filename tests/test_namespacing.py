"""
Test cases for tool namespacing functionality in NorthMCPServer.
"""

import pytest
from north_mcp_python_sdk import NorthMCPServer, _normalize_namespace


class TestNamespaceNormalization:
    """Test the namespace normalization function."""
    
    def test_simple_name(self):
        """Test simple name normalization."""
        assert _normalize_namespace("Demo") == "demo"
        assert _normalize_namespace("Calculator") == "calculator"
    
    def test_name_with_spaces(self):
        """Test name with spaces."""
        assert _normalize_namespace("Slack Dev") == "slack_dev"
        assert _normalize_namespace("My Server") == "my_server"
        assert _normalize_namespace("Basic Calculator") == "basic_calculator"
    
    def test_name_with_special_chars(self):
        """Test name with special characters."""
        assert _normalize_namespace("My-Server") == "my_server"
        assert _normalize_namespace("Calculator 2.0!") == "calculator_2_0"
        assert _normalize_namespace("API@Server#1") == "api_server_1"
    
    def test_name_with_multiple_separators(self):
        """Test name with multiple consecutive separators."""
        assert _normalize_namespace("My---Server") == "my_server"
        assert _normalize_namespace("Test   Space") == "test_space"
        assert _normalize_namespace("Multi___Under") == "multi_under"
    
    def test_edge_cases(self):
        """Test edge cases."""
        assert _normalize_namespace("123") == "123"
        assert _normalize_namespace("___") == "server"
        assert _normalize_namespace("") == "server"
        assert _normalize_namespace("   ") == "server"
        assert _normalize_namespace("!@#$%") == "server"


class TestNorthMCPServerNamespacing:
    """Test the namespacing functionality in NorthMCPServer."""
    
    def test_namespace_enabled_by_default(self):
        """Test that namespacing is enabled by default."""
        server = NorthMCPServer("Test Server")
        assert server._namespace_enabled is True
        assert server._namespace_prefix == "test_server"
    
    def test_namespace_disabled(self):
        """Test that namespacing can be disabled."""
        server = NorthMCPServer("Test Server", namespace=False)
        assert server._namespace_enabled is False
        assert server._namespace_prefix is None
    
    def test_namespace_with_none_name(self):
        """Test namespacing when server name is None."""
        server = NorthMCPServer(None, namespace=True)
        assert server._namespace_enabled is True
        assert server._namespace_prefix is None
    
    def test_get_namespaced_tool_name(self):
        """Test the internal method for getting namespaced tool names."""
        server = NorthMCPServer("Demo", namespace=True)
        assert server._get_namespaced_tool_name("add") == "demo_add"
        assert server._get_namespaced_tool_name("calculate") == "demo_calculate"
    
    def test_get_namespaced_tool_name_disabled(self):
        """Test tool name when namespacing is disabled."""
        server = NorthMCPServer("Demo", namespace=False)
        assert server._get_namespaced_tool_name("add") == "add"
        assert server._get_namespaced_tool_name("calculate") == "calculate"
    
    def test_add_tool_with_namespace(self):
        """Test adding tools with namespacing enabled."""
        server = NorthMCPServer("Calculator", namespace=True)
        
        def add_func(a: int, b: int) -> int:
            return a + b
        
        def multiply_func(a: int, b: int) -> int:
            return a * b
        
        server.add_tool(add_func)
        server.add_tool(multiply_func, name="custom_multiply")
        
        # Check that tools are registered with namespaced names
        tools = server._tool_manager.list_tools()
        tool_names = [tool.name for tool in tools]
        
        assert "calculator_add_func" in tool_names
        assert "calculator_custom_multiply" in tool_names
    
    def test_add_tool_without_namespace(self):
        """Test adding tools with namespacing disabled."""
        server = NorthMCPServer("Calculator", namespace=False)
        
        def add_func(a: int, b: int) -> int:
            return a + b
        
        def multiply_func(a: int, b: int) -> int:
            return a * b
        
        server.add_tool(add_func)
        server.add_tool(multiply_func, name="custom_multiply")
        
        # Check that tools are registered without namespaced names
        tools = server._tool_manager.list_tools()
        tool_names = [tool.name for tool in tools]
        
        assert "add_func" in tool_names
        assert "custom_multiply" in tool_names
    
    def test_tool_decorator_with_namespace(self):
        """Test the @tool decorator with namespacing enabled."""
        server = NorthMCPServer("Math Server", namespace=True)
        
        @server.tool()
        def subtract(a: int, b: int) -> int:
            """Subtract b from a"""
            return a - b
        
        @server.tool(name="divide_numbers")
        def divide(a: float, b: float) -> float:
            """Divide a by b"""
            return a / b
        
        # Check that tools are registered with namespaced names
        tools = server._tool_manager.list_tools()
        tool_names = [tool.name for tool in tools]
        
        assert "math_server_subtract" in tool_names
        assert "math_server_divide_numbers" in tool_names
    
    def test_tool_decorator_without_namespace(self):
        """Test the @tool decorator with namespacing disabled."""
        server = NorthMCPServer("Math Server", namespace=False)
        
        @server.tool()
        def subtract(a: int, b: int) -> int:
            """Subtract b from a"""
            return a - b
        
        @server.tool(name="divide_numbers")
        def divide(a: float, b: float) -> float:
            """Divide a by b"""
            return a / b
        
        # Check that tools are registered without namespaced names
        tools = server._tool_manager.list_tools()
        tool_names = [tool.name for tool in tools]
        
        assert "subtract" in tool_names
        assert "divide_numbers" in tool_names
    
    def test_multiple_servers_different_namespaces(self):
        """Test that multiple servers with different namespaces work independently."""
        calc_server = NorthMCPServer("Calculator", namespace=True)
        slack_server = NorthMCPServer("Slack Dev", namespace=True)
        
        @calc_server.tool()
        def add(a: int, b: int) -> int:
            return a + b
        
        @slack_server.tool()
        def add(channel: str, message: str) -> str:
            return f"Added message to {channel}: {message}"
        
        # Check calculator server tools
        calc_tools = calc_server._tool_manager.list_tools()
        calc_tool_names = [tool.name for tool in calc_tools]
        assert "calculator_add" in calc_tool_names
        
        # Check slack server tools
        slack_tools = slack_server._tool_manager.list_tools()
        slack_tool_names = [tool.name for tool in slack_tools]
        assert "slack_dev_add" in slack_tool_names
        
        # Ensure no cross-contamination
        assert "slack_dev_add" not in calc_tool_names
        assert "calculator_add" not in slack_tool_names
    
    def test_tool_decorator_error_handling(self):
        """Test that the tool decorator handles errors correctly."""
        server = NorthMCPServer("Test", namespace=True)
        
        # Test incorrect usage (passing function directly)
        with pytest.raises(TypeError, match="The @tool decorator was used incorrectly"):
            @server.tool  # Missing parentheses
            def bad_tool():
                pass
