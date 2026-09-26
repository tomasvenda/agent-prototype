import os
import json
from dotenv import load_dotenv
from anthropic import Anthropic
from database import check_availability, book_appointment, cancel_appointment

# Load secure environment variables (Best Practice)
load_dotenv()
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Define the tools (API schemas)
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
"""


def execute_tool(tool_name, tool_args):
    """Router function to execute local Python code based on LLM requests."""
    print(f"\n[SYSTEM: Executing Tool -> {tool_name} with args: {tool_args}]")
    if tool_name == "check_availability":
        return check_availability(tool_args["date"])
    elif tool_name == "book_appointment":
        return book_appointment(tool_args["customer_name"], tool_args["service_type"], tool_args["date"])
    elif tool_name == "cancel_appointment":
        return cancel_appointment(tool_args["customer_name"], tool_args["date"])
    return "Error: Tool not found."

def run_agent():
    print("Welcome to the Dealership After-Sales Portal. Type 'exit' to quit.\n")
    
    messages = []

    while True:
        user_input = input("Customer: ")
        if user_input.lower() == 'exit':
            break

        messages.append({"role": "user", "content": user_input})

        # --- THE CONTINUOUS AGENT LOOP ---
        # This loop keeps running as long as Claude wants to use tools.
        while True:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=500,
                system=SYSTEM_PROMPT,
                tools=workshop_tools,
                messages=messages
            )

            # Check if Claude decided to use a tool
            if response.stop_reason == "tool_use":
                # Add Claude's tool request to the history
                messages.append({"role": "assistant", "content": response.content})
                
                # Find the exact tool Claude wants to use
                tool_use = next(block for block in response.content if block.type == "tool_use")
                
                # Execute our local Python function
                tool_result = execute_tool(tool_use.name, tool_use.input)
                
                # Send the database result back to Claude (Loop continues!)
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": tool_result
                        }
                    ]
                })
                
            else:
                # Claude is finished using tools and wants to talk to the user
                agent_reply = response.content[0].text
                messages.append({"role": "assistant", "content": agent_reply})
                print(f"Agent: {agent_reply}\n")
                
                # Break out of the tool loop to wait for the next human input
                break

if __name__ == "__main__":
    run_agent()