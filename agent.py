import os
from datetime import date
from dotenv import load_dotenv
from anthropic import Anthropic
from database import check_availability, book_appointment, cancel_appointment

load_dotenv()
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MODEL = "claude-haiku-4-5-20251001"

workshop_tools = [
    {
        "name": "check_availability",
        "description": "Check if a specific date is available. Use this before booking and ask for full format date (YYYY-MM-DD).",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format."}
            },
            "required": ["date"]
        }
    },
    {
        "name": "book_appointment",
        "description": "Book a service. Only call this after confirming availability.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_name": {"type": "string"},
                "service_type": {
                    "type": "string",
                    "enum": ["Oil Change", "Tire Rotation", "Brake Inspection", "Full Service / MOT", "General Diagnostics"],
                    "description": "The exact service requested."
                },
                "date": {"type": "string"}
            },
            "required": ["customer_name", "service_type", "date"]
        }
    },
    {
        "name": "cancel_appointment",
        "description": "Cancel an existing service appointment for a customer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_name": {"type": "string"},
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format."}
            },
            "required": ["customer_name", "date"]
        }
    }
]

SYSTEM_PROMPT = """
You are a human-like after-sales automotive assistant.
Help customers check availability, book, and cancel workshop appointments.
Always confirm the date availability before making a booking, requesting full date format YYYY-MM-DD.
Always confirm the name of the customer when cancelling an appointment.
Our workshop currently offers the following services: Oil Change, Tire Rotation, Brake Inspection, Full Service / MOT and General Diagnostics.
Be conversational, concise, and polite. If a user just says hello or gives their name, simply greet them back and ask how you can help without immediately listing all your capabilities.
Reply in plain text without Markdown formatting, as your messages are shown in a simple chat window.
"""


def execute_tool(tool_name, tool_args):
    """Router function to execute local Python code based on LLM requests."""
    print(f"[SYSTEM: Executing Tool -> {tool_name} with args: {tool_args}]")
    if tool_name == "check_availability":
        return check_availability(tool_args["date"])
    elif tool_name == "book_appointment":
        return book_appointment(tool_args["customer_name"], tool_args["service_type"], tool_args["date"])
    elif tool_name == "cancel_appointment":
        return cancel_appointment(tool_args["customer_name"], tool_args["date"])
    return "Error: Tool not found."


def run_agent_turn(messages: list) -> str:
    """
    Runs one customer turn: calls Claude, executes any tools it requests,
    and repeats until Claude produces a final text reply.
    `messages` must already contain the latest user message; it is updated in place.
    """
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=500,
            system=SYSTEM_PROMPT + f"\nToday's date is {date.today().strftime('%A, %Y-%m-%d')}.",
            tools=workshop_tools,
            messages=messages
        )

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            messages.append({"role": "user", "content": tool_results})
        else:
            # Join all text blocks (safer than assuming content[0] is text)
            agent_reply = "".join(b.text for b in response.content if b.type == "text")
            messages.append({"role": "assistant", "content": agent_reply})
            return agent_reply