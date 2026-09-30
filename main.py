from database import init_db
from agent import run_agent_turn

def run_cli():
    init_db()
    print("Welcome to the Dealership After-Sales Portal. Type 'exit' to quit.\n")

    messages = []
    while True:
        user_input = input("Customer: ")
        if user_input.lower() == "exit":
            break

        messages.append({"role": "user", "content": user_input})
        reply = run_agent_turn(messages)
        print(f"Agent: {reply}\n")

if __name__ == "__main__":
    run_cli()