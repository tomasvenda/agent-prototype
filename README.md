# Workshop Assistant

An AI assistant that books, checks, and cancels car workshop appointments through natural conversation.

Built with Claude (tool calling), FastAPI, SQLite, Docker, and MLflow.

## How it works

The customer chats with Claude. When Claude needs real information, it calls one of three Python tools (`check_availability`, `book_appointment`, `cancel_appointment`) that read and write a SQLite database. Claude never invents a booking: every answer comes from the database.

The same tools are also available as a REST API and as an MCP server for Claude Desktop.

## Run it

You need [Docker Desktop](https://www.docker.com/products/docker-desktop/) and an [Anthropic API key](https://console.anthropic.com).

```bash
git clone https://github.com/<your-username>/workshop-assistant.git
cd workshop-assistant
cp .env.example .env
```

Open `.env` and add your API key, then:

```bash
docker compose up --build
```

Open **http://localhost:8000** to chat, or **http://localhost:8000/docs** to try the API.

## Evaluation

The agent is tested with 11 scripted scenarios: booking, full days, unknown services, missing information, multi-turn conversations, and cancellations. Each scenario runs 3 times, and success is checked against the final database state and the tools Claude called, not its wording. Results are tracked with MLflow.

The first evaluation found a real bug: asked for "next Tuesday", Claude booked a Monday every time, while telling the customer it was a Tuesday. Prompt v2 gives Claude a generated calendar so it looks dates up instead of calculating them.

| | Prompt v1 | Prompt v2 |
|---|---|---|
| Pass rate | 91% | **100%** |
| "Next Tuesday" scenario | 0/3 | **3/3** |
| Tokens per conversation | 3,600 | 4,778 |
| Latency per reply | 1.78s | 1.86s |

The fix costs about 30% more tokens per conversation, with no regressions in the other scenarios.

To run the evaluation yourself (this makes real API calls, typically well under 1 USD):

```bash
pip install -r requirements.txt mlflow
python evals/compare.py
mlflow server --backend-store-uri sqlite:///mlflow.db --port 5000
```

Then open **http://127.0.0.1:5000** to compare the runs.

## Project structure

```
agent.py        Claude, the tools, and the agent loop
api.py          FastAPI: chat endpoint, REST endpoints, web page
database.py     SQLite queries and booking rules
server.py       MCP server for Claude Desktop
main.py         Chat in the terminal
static/         The chat web page
evals/          Test scenarios, evaluation runner, MLflow logging
```

## Why I built this

To learn how to build reliable AI agents in practice: keeping the model inside strict tool boundaries, letting code (not the prompt) enforce the rules, and measuring the agent's behavior instead of trusting it.
