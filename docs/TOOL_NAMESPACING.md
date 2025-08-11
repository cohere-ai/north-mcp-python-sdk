# Tool Namespacing in North MCP Python SDK

## Overview

The North MCP Python SDK includes built-in tool namespacing functionality to prevent tool name collisions when multiple MCP servers are used together. This feature automatically prefixes tool names with a normalized version of the server name.

## Why Tool Namespacing?

When multiple MCP servers are running in the same environment, tool name collisions can occur. For example:

- A calculator server might have an `add` tool for mathematical operations
- A Slack server might have an `add` tool for adding users to channels
- A database server might have an `add` tool for inserting records

Without namespacing, these tools would conflict. With namespacing enabled, they become:

- `calculator_add`
- `slack_add` 
- `database_add`

## Usage

### Basic Usage

Namespacing is **enabled by default** when you create a `NorthMCPServer`:

```python
from north_mcp_python_sdk import NorthMCPServer

# Create server with namespacing enabled (default)
mcp = NorthMCPServer("Demo Calculator", port=5222)

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

@mcp.tool()
def multiply(a: int, b: int) -> int:
    """Multiply two numbers"""
    return a * b

# Tools will be registered as:
# - demo_calculator_add
# - demo_calculator_multiply
```

### Disabling Namespacing

You can disable namespacing by setting `namespace=False`:

```python
# Create server without namespacing
mcp = NorthMCPServer("Simple Server", namespace=False)

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

# Tool will be registered as:
# - add (no prefix)
```

### Custom Tool Names

Custom tool names work with namespacing:

```python
mcp = NorthMCPServer("Math Server", namespace=True)

@mcp.tool(name="custom_division")
def divide(a: float, b: float) -> float:
    """Divide two numbers"""
    return a / b

# Tool will be registered as:
# - math_server_custom_division
```

## Namespace Normalization

Server names are automatically normalized to create valid namespace identifiers:

| Server Name | Normalized Namespace |
|-------------|---------------------|
| `"Demo"` | `demo` |
| `"Slack Dev"` | `slack_dev` |
| `"My-Server"` | `my_server` |
| `"Calculator 2.0!"` | `calculator_2_0` |
| `"API@Server#1"` | `api_server_1` |

The normalization process:

1. Converts to lowercase
2. Replaces non-alphanumeric characters with underscores
3. Removes leading/trailing underscores
4. Collapses multiple consecutive underscores into single underscores
5. Falls back to `"server"` for empty or invalid names

## Examples

### Multiple Servers Without Collisions

```python
from north_mcp_python_sdk import NorthMCPServer

# Calculator server
calc_server = NorthMCPServer("Basic Calculator", port=5222)

@calc_server.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

@calc_server.tool()
def calculate(expression: str) -> str:
    """Evaluate mathematical expression"""
    return str(eval(expression))

# Slack server  
slack_server = NorthMCPServer("Slack Dev", port=5223)

@slack_server.tool()
def add(channel: str, user: str) -> dict:
    """Add user to channel"""
    return {"added": user, "to": channel}

@slack_server.tool()
def list_channels() -> list:
    """List all channels"""
    return [{"name": "general"}, {"name": "random"}]

# Resulting tools:
# Calculator: basic_calculator_add, basic_calculator_calculate
# Slack: slack_dev_add, slack_dev_list_channels
```

### Mixed Namespacing

```python
# Namespaced server
namespaced = NorthMCPServer("Special Tools", namespace=True)

@namespaced.tool()
def special_function() -> str:
    return "namespaced"

# Non-namespaced server
simple = NorthMCPServer("Simple Tools", namespace=False)

@simple.tool()
def simple_function() -> str:
    return "not namespaced"

# Resulting tools:
# - special_tools_special_function
# - simple_function
```

## API Reference

### NorthMCPServer Parameters

```python
def __init__(
    self,
    name: str | None = None,
    instructions: str | None = None,
    server_secret: str | None = None,
    auth_server_provider: OAuthAuthorizationServerProvider | None = None,
    debug: bool | None = None,
    namespace: bool = True,  # NEW: Enable/disable namespacing
    **settings: Any,
):
```

**Parameters:**

- `namespace` (bool, default=True): Whether to enable tool namespacing
  - `True`: Tools are prefixed with normalized server name using underscore separator
  - `False`: Tools use their original names without prefixes

### Utility Functions

```python
from north_mcp_python_sdk import _normalize_namespace

# Get normalized namespace for a server name
namespace = _normalize_namespace("My Server 2.0!")
print(namespace)  # Output: "my_server_2_0"
```

## Best Practices

1. **Use descriptive server names**: The server name becomes the namespace prefix, so choose names that clearly identify the server's purpose.

2. **Keep namespaces consistent**: If you're building a suite of related servers, use consistent naming patterns.

3. **Consider namespace length**: Very long server names result in long tool names. Keep server names reasonably concise.

4. **Test tool names**: Use the provided examples or tests to verify your tool names are what you expect.

5. **Document your tools**: Include clear descriptions for tools, especially when namespacing creates longer tool names.

## Troubleshooting

### Tool Names Not What Expected

Check the normalized namespace:

```python
server = NorthMCPServer("Your Server Name")
print(f"Namespace: {server._namespace_prefix}")

tools = server._tool_manager.list_tools()
for tool in tools:
    print(f"Tool: {tool.name}")
```

### Disabling Namespacing Temporarily

For debugging or migration purposes:

```python
# Temporarily disable namespacing
server = NorthMCPServer("My Server", namespace=False)
```

### Custom Namespace Logic

If you need custom namespace logic, you can subclass `NorthMCPServer`:

```python
class CustomNorthMCPServer(NorthMCPServer):
    def _get_namespaced_tool_name(self, name: str) -> str:
        # Custom namespace logic here
        if self._namespace_enabled:
            return f"custom_{self._namespace_prefix}_{name}"
        return name
```

## Migration Guide

### From Non-Namespaced to Namespaced

If you're migrating existing servers to use namespacing:

1. **Identify current tool names** in your MCP clients
2. **Update client code** to use the new namespaced tool names
3. **Test thoroughly** to ensure all tool calls work correctly

### Gradual Migration

You can migrate gradually by running both versions:

```python
# Old server (no namespacing)
old_server = NorthMCPServer("Calculator", port=5222, namespace=False)

# New server (with namespacing)  
new_server = NorthMCPServer("Calculator", port=5223, namespace=True)

# Gradually migrate clients from port 5222 to 5223
```
