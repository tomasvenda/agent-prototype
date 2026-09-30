"""
Plays every scenario in scenarios.json against the agent, checks the
expectations, and prints metrics.

Run from the project folder:
    python evals/run_evals.py
"""
import json
import os
import sqlite3
import sys
from collections import Counter
from datetime import date
from pathlib import Path

# ======================================================================
# SETUP: find the project, and use a separate database for evaluations
# ======================================================================

EVALS_DIR = Path(__file__).resolve().parent        # .../workshop-assistant/evals
PROJECT_DIR = EVALS_DIR.parent                     # .../workshop-assistant
sys.path.insert(0, str(PROJECT_DIR))               # so Python can find agent.py and database.py

# Must be set BEFORE importing database: the path is read at import time
os.environ["WORKSHOP_DB_PATH"] = str(EVALS_DIR / "eval_workshop.db")

import database                                          # noqa: E402
from agent import run_agent_turn_detailed, MODEL, SYSTEM_PROMPT  # noqa: E402
import mlflow                                            # noqa: E402

EXPERIMENT_NAME = "workshop-agent-evals"
mlflow.set_tracking_uri(f"sqlite:///{(PROJECT_DIR / 'mlflow.db').as_posix()}")

if mlflow.get_experiment_by_name(EXPERIMENT_NAME) is None:
    mlflow.create_experiment(EXPERIMENT_NAME, artifact_location=(PROJECT_DIR / "mlartifacts").as_uri())
mlflow.set_experiment(EXPERIMENT_NAME)


# ======================================================================
# SETTINGS
# ======================================================================

REPEATS = 3                     # how many times each scenario is played
PRICE_INPUT_PER_MTOK = 1.00     # USD per million input tokens (Haiku 4.5; check current pricing)
PRICE_OUTPUT_PER_MTOK = 5.00    # USD per million output tokens


# ======================================================================
# HELPERS
# ======================================================================

def reset_database(seed: list):
    """Empty the eval database, then insert the scenario's starting bookings."""
    database.init_db()
    conn = sqlite3.connect(database.DB_PATH)
    conn.execute("DELETE FROM appointments")
    conn.commit()
    conn.close()
    for appt in seed:
        database.create_appointment(appt["customer_name"], appt["service_type"], appt["date"])


def as_counter(appointments: list) -> Counter:
    """Turn a list of appointments into a comparable 'bag' (order ignored, duplicates counted)."""
    return Counter((a["customer_name"], a["service_type"], a["date"]) for a in appointments)


def checked_before_booking(tool_names: list) -> bool:
    """True if every book_appointment call comes after at least one check_availability."""
    checked = False
    for name in tool_names:
        if name == "check_availability":
            checked = True
        elif name == "book_appointment" and not checked:
            return False
    return True


# ======================================================================
# PLAY ONE SCENARIO
# ======================================================================

def run_scenario(scenario: dict, model: str, system_prompt: str, show_calendar: bool) -> dict:
    reset_database(scenario["seed"])
    today = date.fromisoformat(scenario["today"])

    messages, all_tool_calls, transcript = [], [], []
    input_tokens = output_tokens = llm_calls = 0
    latency = 0.0

    # Play the customer's messages one by one, in the same conversation
    for customer_message in scenario["turns"]:
        messages.append({"role": "user", "content": customer_message})
        turn = run_agent_turn_detailed(
            messages, model=model, system_prompt=system_prompt,
            today=today, show_calendar=show_calendar,
        )

        all_tool_calls += turn.tool_calls
        input_tokens += turn.input_tokens
        output_tokens += turn.output_tokens
        llm_calls += turn.llm_calls
        latency += turn.latency_seconds
        transcript.append({"customer": customer_message, "agent": turn.reply, "tools": turn.tool_calls})

    # Check the expectations
    expect = scenario["expect"]
    tool_names = [call["name"] for call in all_tool_calls]

    checks = {
        "db_state": as_counter(database.list_appointments()) == as_counter(expect["final_appointments"]),
        "must_call": all(tool in tool_names for tool in expect["must_call"]),
        "must_not_call": not any(tool in tool_names for tool in expect["must_not_call"]),
        "check_before_book": checked_before_booking(tool_names) if expect["check_before_book"] else True,
    }

    return {
        "scenario": scenario["id"],
        "passed": all(checks.values()),
        "checks": checks,
        "turns": len(scenario["turns"]),
        "tool_calls": len(all_tool_calls),
        "tool_errors": sum(call["is_error"] for call in all_tool_calls),
        "llm_calls": llm_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_seconds": latency,
        "transcript": transcript,
        "error": None,
    }


def crashed_result(scenario: dict, error: Exception) -> dict:
    """If a run crashes (network error, rate limit...), record it as a failure and keep going."""
    return {
        "scenario": scenario["id"], "passed": False,
        "checks": {"db_state": False, "must_call": False, "must_not_call": False, "check_before_book": False},
        "turns": len(scenario["turns"]), "tool_calls": 0, "tool_errors": 0, "llm_calls": 0,
        "input_tokens": 0, "output_tokens": 0, "latency_seconds": 0.0,
        "transcript": [], "error": str(error),
    }


# ======================================================================
# METRICS
# ======================================================================

def compute_metrics(results: list) -> dict:
    n = len(results)
    total_turns = sum(r["turns"] for r in results)
    total_tool_calls = sum(r["tool_calls"] for r in results)
    total_input = sum(r["input_tokens"] for r in results)
    total_output = sum(r["output_tokens"] for r in results)

    def rate(check_name):
        return sum(r["checks"][check_name] for r in results) / n

    return {
        # Quality
        "pass_rate": sum(r["passed"] for r in results) / n,
        "db_state_accuracy": rate("db_state"),
        "must_call_rate": rate("must_call"),
        "must_not_call_rate": rate("must_not_call"),
        "check_before_book_rate": rate("check_before_book"),
        "tool_error_rate": sum(r["tool_errors"] for r in results) / total_tool_calls if total_tool_calls else 0.0,
        # Efficiency
        "avg_latency_per_turn": sum(r["latency_seconds"] for r in results) / total_turns,
        "avg_llm_calls_per_turn": sum(r["llm_calls"] for r in results) / total_turns,
        "avg_tokens_per_conversation": (total_input + total_output) / n,
        "total_cost_usd": total_input / 1e6 * PRICE_INPUT_PER_MTOK + total_output / 1e6 * PRICE_OUTPUT_PER_MTOK,
        # Reliability
        "crashed_runs": sum(r["error"] is not None for r in results),
    }


# ======================================================================
# REPORT
# ======================================================================

def print_report(results: list, metrics: dict):
    print("\n" + "=" * 64)
    print("RESULTS PER SCENARIO")
    print("=" * 64)

    scenario_ids = list(dict.fromkeys(r["scenario"] for r in results))   # keeps original order
    for sid in scenario_ids:
        runs = [r for r in results if r["scenario"] == sid]
        passes = sum(r["passed"] for r in runs)
        status = "PASS " if passes == len(runs) else ("FAIL " if passes == 0 else "FLAKY")

        # Which checks failed, and how often
        failed = Counter(name for r in runs for name, ok in r["checks"].items() if not ok)
        details = ", ".join(f"{name} x{count}" for name, count in failed.items())

        print(f"{status}  {sid:<28} {passes}/{len(runs)}   {details}")

    print("\n" + "=" * 64)
    print("METRICS")
    print("=" * 64)
    for name, value in metrics.items():
        if name.endswith("_rate") or name.endswith("_accuracy"):
            print(f"{name:<30} {value:.0%}")
        elif name == "total_cost_usd":
            print(f"{name:<30} ${value:.4f}")
        elif isinstance(value, float):
            print(f"{name:<30} {value:.2f}")
        else:
            print(f"{name:<30} {value}")


# ======================================================================
# MLFLOW
# ======================================================================

def format_failed_conversations(results: list) -> str:
    """A readable text of every failed run: what the customer said, which tools Claude used, what it replied."""
    lines = []
    for r in results:
        if r["passed"]:
            continue
        failed_checks = [name for name, ok in r["checks"].items() if not ok]
        lines.append("=" * 70)
        lines.append(f"SCENARIO: {r['scenario']}   FAILED CHECKS: {', '.join(failed_checks)}")
        if r["error"]:
            lines.append(f"CRASH: {r['error']}")
        for turn in r["transcript"]:
            lines.append(f"\nCUSTOMER: {turn['customer']}")
            for call in turn["tools"]:
                lines.append(f"   [tool] {call['name']}({call['input']}) -> {call['output']}")
            lines.append(f"AGENT: {turn['agent']}")
        lines.append("")
    return "\n".join(lines) if lines else "All runs passed."


def log_to_mlflow(results: list, metrics: dict, model: str, system_prompt: str,
                  prompt_version: str, show_calendar: bool):
    """Save one evaluation as one MLflow run."""
    scenario_ids = list(dict.fromkeys(r["scenario"] for r in results))

    with mlflow.start_run(run_name=f"prompt {prompt_version} | {model}"):
        # Parameters: what we chose
        mlflow.log_params({
            "model": model,
            "prompt_version": prompt_version,
            "show_calendar": show_calendar,
            "repeats": REPEATS,
            "num_scenarios": len(scenario_ids),
        })

        # Metrics: what we measured (overall)
        mlflow.log_metrics(metrics)

        # Metrics: pass rate of each individual scenario
        for sid in scenario_ids:
            runs = [r for r in results if r["scenario"] == sid]
            mlflow.log_metric(f"scenario/{sid}", sum(r["passed"] for r in runs) / len(runs))

        # Artifacts: files attached to the run
        mlflow.log_text(system_prompt, "system_prompt.txt")
        mlflow.log_text(format_failed_conversations(results), "failed_conversations.txt")
        mlflow.log_dict(results, "results.json")

    print("\nLogged to MLflow experiment 'workshop-agent-evals'.")

# ======================================================================
# MAIN
# ======================================================================

def main(model: str = MODEL, system_prompt: str = SYSTEM_PROMPT,
         prompt_version: str = "v1", show_calendar: bool = False):  
    with open(EVALS_DIR / "scenarios.json", encoding="utf-8") as f:
        scenarios = json.load(f)

    total = len(scenarios) * REPEATS
    print(f"Running {len(scenarios)} scenarios x {REPEATS} repeats = {total} runs with {model}\n")

    results = []
    count = 0
    for scenario in scenarios:
        for repeat in range(1, REPEATS + 1):
            count += 1
            try:
                result = run_scenario(scenario, model, system_prompt, show_calendar)
            except Exception as e:
                result = crashed_result(scenario, e)
            results.append(result)

            outcome = "PASS" if result["passed"] else ("CRASH" if result["error"] else "FAIL")
            print(f"  [{count}/{total}] {scenario['id']} (run {repeat}) -> {outcome}")

    metrics = compute_metrics(results)
    print_report(results, metrics)
    log_to_mlflow(results, metrics, model, system_prompt, prompt_version, show_calendar)  
    return results, metrics


if __name__ == "__main__":
    main()