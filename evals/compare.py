"""
Runs the evaluation for several agent configurations, one MLflow run each.

Run from the project folder:
    python evals/compare.py
"""
import run_evals                                    # sets up paths, eval database and MLflow
from agent import MODEL, SYSTEM_PROMPT, SYSTEM_PROMPT_V2

CONFIGURATIONS = [
    {"prompt_version": "v1", "system_prompt": SYSTEM_PROMPT, "show_calendar": False, "model": MODEL},
    {"prompt_version": "v2", "system_prompt": SYSTEM_PROMPT_V2, "show_calendar": True, "model": MODEL},
]

for config in CONFIGURATIONS:
    print("\n" + "#" * 64)
    print(f"# CONFIGURATION: prompt {config['prompt_version']}")
    print("#" * 64)
    run_evals.main(**config)