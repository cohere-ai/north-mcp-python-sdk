
from typing import List
from pydantic import BaseModel, Field
from north_mcp_python_sdk import NorthMCPServer

_default_port = 3001

# update all the mcp tool functions to be <firstname_lastname>_<tool>
# since mcp tool names MUST be unique

mcp = NorthMCPServer(
    "Simple Calculator", host="0.0.0.0", port=_default_port
)

@mcp.tool()
def firstname_lastname_add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


@mcp.tool()
def firstname_lastname_subtract(a: int, b: int) -> int:
    """Subtract two numbers"""
    return a - b


@mcp.tool()
def firstname_lastname_multiply(a: int, b: int) -> int:
    """Multiply two numbers"""
    return a * b


# destructiveHint due to possible division by zero etc. issues
# The destructiveHint doesn’t prevent division by zero,
# but it allows the system to warn or double-check with the user before running potentially dangerous operations. 
# In this case, it’s about safety and user awareness, not automatic error handling.
@mcp.tool(annotations={"destructiveHint":  True})
def firstname_lastname_divide(a: int, b: int) -> int:
    """Divide two numbers"""
    return int(a / b)


@mcp.tool()
def firstname_lastname_exponent(a: int, b: int) -> int:
    """
    Raises the first number to the power of the second number.
    Exponent two numbers"""
    return a**b


@mcp.tool()
def firstname_lastname_modulo(a: int, b: int) -> int:
    """Modulo two numbers"""
    return a % b


class CalculationRequest(BaseModel):
    """Pydantic model for batch calculations"""
    operation: str = Field(description="Operation to perform: 'add', 'subtract', 'multiply', 'divide', 'average'")
    numbers: List[float] = Field(description="List of numbers to operate on")
    precision: int = Field(default=2, description="Decimal precision for the result")



@mcp.tool()
def firstname_lastname_batch_calculate(request: CalculationRequest) -> dict:
    """Perform batch calculations using a Pydantic model
    ie add multiple numbers
    batch_calculate(CalculationRequest(
        operation="add",
        numbers=[5, 3, 7, 2],
        precision=2
    ))
    """
    numbers = request.numbers
    operation = request.operation.lower()
    precision = request.precision
    
    if len(numbers) == 0:
        return {"error": "No numbers provided"}
    
    result = 0.0
    
    if operation == "add":
        result = sum(numbers)
    
    elif operation == "subtract":
        result = numbers[0] if numbers else 0
        for num in numbers[1:]:
            result -= num
    
    elif operation == "multiply":
        result = 1
        for num in numbers:
            result *= num
    
    elif operation == "divide":
        if 0 in numbers[1:]:
            return {"error": "Cannot divide by zero"}
        result = numbers[0] if numbers else 0
        for num in numbers[1:]:
            result /= num
    
    elif operation == "average":
        result = sum(numbers) / len(numbers)
    
    else:
        return {"error": f"Unknown operation: {operation}"}
    
    return {
        "operation": operation,
        "input_numbers": numbers,
        "result": round(result, precision),
        "precision": precision
    }


# Use streamable-http transport to enable streaming responses over HTTP.
# This allows the server to send data to the client incrementally (in chunks),
# improving responsiveness for long-running or large operations.
if __name__ == "__main__":
    mcp.run(transport="streamable-http")
