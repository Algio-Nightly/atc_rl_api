"""
Test script to inspect the prompts generated for the LLM.

Runs the ATC environment and prints the system prompt + per-step user prompt
without calling any LLM. Advances the simulation with no-op actions each step.
"""

import time
import sys

from rl_env.environment import ATCEnv
from rl_env.models import ATCAction
from rl_env.prompts.atc_prompt import generate_atc_prompt

# Import the system prompt from inference
from inference import SYSTEM_PROMPT

TASKS = ["single_approach", "multi_departure", "traffic_pattern"]
MAX_STEPS = 10
STEP_DELAY = 3


def run_task(task_name: str) -> None:
    env = ATCEnv()
    observation, info = env.reset(task=task_name)

    print("=" * 80)
    print(f"  TASK: {task_name}")
    print("=" * 80)

    print("\n┌─── SYSTEM PROMPT ───┐\n")
    print(SYSTEM_PROMPT)
    print("\n└─────────────────────┘\n")

    for step in range(1, MAX_STEPS + 1):
        prompt = generate_atc_prompt(observation)

        print(f"\n{'─' * 80}")
        print(f"  STEP {step} — USER PROMPT")
        print(f"{'─' * 80}\n")
        print(prompt)
        print(f"\n{'─' * 80}")

        # No-op action (no commands)
        action = ATCAction(commands=[])
        observation, reward, done, _truncated, _info = env.step(action)

        print(f"  [reward={reward:.2f}  done={done}]")

        if done:
            print("\n  Episode terminated.")
            break

        time.sleep(STEP_DELAY)

    env.close()


def main() -> None:
    task = TASKS[0]

    if len(sys.argv) > 1:
        task = sys.argv[1]
        if task not in TASKS:
            print(f"Unknown task '{task}'. Available: {', '.join(TASKS)}")
            sys.exit(1)

    run_task(task)


if __name__ == "__main__":
    main()
