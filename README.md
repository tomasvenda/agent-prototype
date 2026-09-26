# Autoflows Prototype: Agentic After-Sales Assistant

A lightweight, function-calling conversational agent built to demonstrate an understanding of agentic workflows, tool-calling schemas, and LLM-to-Database integrations.

## Architecture & Tools
* **LLM:** Claude Haiku 4.5 (chosen for speed, high context window, and cost-efficiency in conversational routing).
* **Integration:** Python `sqlite3` mocking a local dealership database.
* **Agentic Workflow:** The orchestrator utilizes Anthropic's tool-calling schema to programmatically halt generation, execute local Python functions (`check_availability`, `book_appointment`, `cancel_appointment`), and pass the deterministic database results back to the LLM for the final user response.

## Why I Built This
While I understand the theoretical math behind attention mechanisms and tokenization from my Deep Learning coursework, building reliable production agents requires a different approach. I built this to experiment with strict function-calling boundaries—ensuring the LLM cannot hallucinate an appointment that doesn't exist in the database, relying on System Prompts for static data (service menus), and forcing it to handle programmatic rejection.