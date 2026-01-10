from fastmcp import FastMCP
import random


mcp = FastMCP("test-mcp-cloude")


@mcp.tool()
def add_two_numbers(a:float, b:float):
    """add two number together 
    a: float 
    b: float
    return a + b
    """
    
    return a + b


@mcp.tool()
def genrate_random_numbers(n:int = 100):
    """
    generate random numbers between 1 and 100
    """
    
    return [random.randint(1, n) for _ in range(1, n)]


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000) 