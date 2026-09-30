# Workshop Assistant

An AI assistant that books, checks, and cancels car workshop appointments through natural conversation.

Built with Claude (tool calling), FastAPI, SQLite, and Docker.

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

## Project structure

```
agent.py        Claude, the tools, and the agent loop
api.py          FastAPI: chat endpoint, REST endpoints, web page
database.py     SQLite queries and booking rules
server.py       MCP server for Claude Desktop
main.py         Chat in the terminal
static/         The chat web page
```

## Why I built this

To learn how to build reliable AI agents in practice: keeping the model inside strict tool boundaries, letting code (not the prompt) enforce the rules, and turning a script into a small service that anyone can run.
