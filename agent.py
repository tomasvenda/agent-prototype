import os
import time                                   
from dataclasses import dataclass, field      
from datetime import date, timedelta
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

SYSTEM_PROMPT_V2 = SYSTEM_PROMPT + """
Dates:
- Never calculate dates or weekdays yourself. Always look them up in the calendar provided below.
- "Next <weekday>" means the first such day after today. For example, if today is Friday, "next Tuesday" is the Tuesday four days later.
- Tool dates must use the YYYY-MM-DD format.
- When you mention a date to the customer, give the weekday and the date exactly as written in the calendar.
"""

def build_calendar(today: date, days: int = 21) -> str:
    """A list of the coming days with their weekdays, so Claude never has to compute them."""
    lines = []
    for offset in range(days + 1):
        day = today + timedelta(days=offset)
        label = " (today)" if offset == 0 else ""
        lines.append(f"- {day.strftime('%A %Y-%m-%d')}{label}")
    return "Calendar:\n" + "\n".join(lines)


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


@dataclass
class TurnResult:
    reply: str
    tool_calls: list = field(default_factory=list)   # one dict per tool call
    input_tokens: int = 0
    output_tokens: int = 0
    llm_calls: int = 0                                # how many times Claude was called
    latency_seconds: float = 0.0


def run_agent_turn_detailed(
    messages: list,
    model: str = MODEL,
    system_prompt: str = SYSTEM_PROMPT,
    today: date | None = None,
    show_calendar: bool = False,                    
) -> TurnResult:
    """
    Same loop as before, but records tool calls, tokens and latency.
    `model`, `system_prompt`, `today` and `show_calendar` can be changed for experiments.
    """
    today = today or date.today()
    result = TurnResult(reply="")
    start = time.perf_counter()

    # NEW: the date information added to the system prompt
    date_context = f"\nToday's date is {today.strftime('%A, %Y-%m-%d')}."
    if show_calendar:
        date_context += "\n" + build_calendar(today)

    while True:
        response = client.messages.create(
            model=model,
            max_tokens=500,
            system=system_prompt + date_context,    # CHANGED
            tools=workshop_tools,
            messages=messages
        )

        # Count every call to Claude and the tokens it used
        result.llm_calls += 1
        result.input_tokens += response.usage.input_tokens
        result.output_tokens += response.usage.output_tokens

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    output = execute_tool(block.name, block.input)

                    # Remember what Claude did
                    result.tool_calls.append({
                        "name": block.name,
                        "input": block.input,
                        "output": output,
                        "is_error": output.startswith("Error:"),
                    })

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output
                    })

            messages.append({"role": "user", "content": tool_results})
        else:
            result.reply = "".join(b.text for b in response.content if b.type == "text")
            messages.append({"role": "assistant", "content": result.reply})
            result.latency_seconds = time.perf_counter() - start
            return result


def run_agent_turn(messages: list) -> str:
    """The simple version used by api.py and main.py: just the reply text."""
    return run_agent_turn_detailed(messages, system_prompt=SYSTEM_PROMPT_V2, show_calendar=True).reply