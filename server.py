from typing import Literal
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
import database as db

# Make sure the table exists before any tool is used
db.init_db()

# The server object. The name is what hosts like Claude Desktop display.
mcp = MCPServer("Workshop Assistant")

# Same allowed values as the REST API and the agent
ServiceType = Literal[
    "Oil Change", "Tire Rotation", "Brake Inspection", "Full Service / MOT", "General Diagnostics"
]


def _result_or_error(result: str) -> str:
    """Our database functions report problems as sentences starting with 'Error:'.
    MCP has a proper way to flag a failed tool call, so we convert them."""
    if result.startswith("Error:"):
        raise ToolError(result)
    return result


@mcp.tool()
def check_availability(date: str) -> str:
    """Check if the workshop has open slots on a date. The date must be in YYYY-MM-DD format."""
    return _result_or_error(db.check_availability(date))


@mcp.tool()
def book_appointment(customer_name: str, service_type: ServiceType, date: str) -> str:
    """Book a workshop service for a customer on a date (YYYY-MM-DD).
    Always check availability first and confirm the details with the customer."""
    return _result_or_error(db.book_appointment(customer_name, service_type, date))


@mcp.tool()
def cancel_appointment(customer_name: str, date: str) -> str:
    """Cancel a customer's existing appointment on a date (YYYY-MM-DD).
    Confirm the customer's name before cancelling."""
    return _result_or_error(db.cancel_appointment(customer_name, date))


if __name__ == "__main__":
    mcp.run()