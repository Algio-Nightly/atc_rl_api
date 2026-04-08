"""
Competition baseline inference script for the ATC RL Environment.

MANDATORY environment variables:
    API_BASE_URL   The API endpoint for the LLM.
    MODEL_NAME     The model identifier to use for inference.
    HF_TOKEN       Your Hugging Face / API key.

STDOUT FORMAT:
    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>
"""

import os
import sys
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from openai import OpenAI

from rl_env.environment import ATCEnv
from rl_env.models import ATCAction
from rl_env.prompts.atc_prompt import generate_atc_prompt
from rl_env.parsers import parse, ParseError

# ---------------------------------------------------------------------------
# Configuration (overridable via env vars)
# ---------------------------------------------------------------------------

API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")

BENCHMARK_NAME = "atc-rl-env"
MAX_STEPS_PER_EPISODE = 200
LLM_TEMPERATURE = 0.7
LLM_MAX_TOKENS = 1024
SUCCESS_SCORE_THRESHOLD = 0.1

TASKS = ["single_approach", "traffic_pattern", "storm_traffic"]


# ---------------------------------------------------------------------------
# Structured logging helpers
# ---------------------------------------------------------------------------


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(
    step: int, action: str, reward: float, done: bool, error: Optional[str]
) -> None:
    done_str = str(done).lower()
    error_str = error if error else "null"
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} "
        f"done={done_str} error={error_str}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: list[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} "
        f"score={score:.2f} rewards={rewards_str}",
        flush=True,
    )


# ---------------------------------------------------------------------------
# LLM interaction (OpenAI client — mandatory per competition rules)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are an Air Traffic Controller managing radar approaches. "
    "Issue ATC commands in the exact format: ATC <COMMAND> <CALLSIGN> [VALUE]. "
    "Respond ONLY with commands, one per line."
)


def get_llm_response(client: OpenAI, prompt: str) -> str:
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            stream=False,
        )
        return (completion.choices[0].message.content or "").strip()
    except Exception as exc:
        print(f"[DEBUG] LLM request failed: {exc}", flush=True)
        return ""


# ---------------------------------------------------------------------------
# Command parsing
# ---------------------------------------------------------------------------


def build_commands_from_response(llm_text: str) -> tuple[list[str], Optional[str]]:
    """Parse raw LLM text into structured ATC command strings.

    Returns (commands, error_string_or_None).
    """
    if not llm_text.strip():
        return [], "empty_response"

    commands: list[str] = []
    error: Optional[str] = None

    try:
        parsed = parse(llm_text)
        items = parsed if isinstance(parsed, list) else [parsed]

        for cmd in items:
            cmd_str = f"ATC {cmd['command']} {cmd['callsign']}"
            for key in ("heading", "altitude", "speed", "waypoint", "runway"):
                if key in cmd:
                    value = cmd[key]
                    cmd_str += f" TO {value}" if key == "waypoint" else f" {value}"
                    break
            commands.append(cmd_str)
    except ParseError as exc:
        error = f"parse_error:{exc}"
    except Exception as exc:
        error = f"error:{exc}"

    return commands, error


# ---------------------------------------------------------------------------
# Score normalisation — maps cumulative reward to [0, 1]
# ---------------------------------------------------------------------------

MAX_REWARD_PER_STEP = 5.0


def normalize_score(cumulative_reward: float, steps_taken: int) -> float:
    """Clamp score into [0, 1]."""
    if steps_taken <= 0:
        return 0.0
    theoretical_max = steps_taken * MAX_REWARD_PER_STEP
    if theoretical_max <= 0:
        return 0.0
    score = cumulative_reward / theoretical_max
    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Episode runner
# ---------------------------------------------------------------------------


def run_episode(
    env: ATCEnv,
    client: OpenAI,
    task_name: str,
) -> tuple[bool, int, float, list[float]]:
    observation, _info = env.reset(task=task_name)
    rewards: list[float] = []
    steps_taken = 0
    success = False

    log_start(task=task_name, env=BENCHMARK_NAME, model=MODEL_NAME)

    try:
        for step_num in range(1, MAX_STEPS_PER_EPISODE + 1):
            steps_taken = step_num

            prompt = generate_atc_prompt(observation)
            llm_text = get_llm_response(client, prompt)
            commands, parse_error = build_commands_from_response(llm_text)

            action = ATCAction(commands=commands)
            action_str = "; ".join(commands) if commands else "NOOP"

            try:
                observation, reward, done, _truncated, _info = env.step(action)
                rewards.append(reward)

                log_step(
                    step=step_num,
                    action=action_str,
                    reward=reward,
                    done=done,
                    error=parse_error,
                )

                if done:
                    break

            except Exception as exc:
                rewards.append(0.0)
                log_step(
                    step=step_num,
                    action=action_str,
                    reward=0.0,
                    done=True,
                    error=f"step_error:{exc}",
                )
                break

    except Exception as exc:
        if steps_taken == 0:
            steps_taken = 1
        rewards.append(0.0)
        log_step(
            step=steps_taken,
            action="ERROR",
            reward=0.0,
            done=True,
            error=f"episode_error:{exc}",
        )

    score = normalize_score(sum(rewards), steps_taken)
    success = score >= SUCCESS_SCORE_THRESHOLD

    log_end(success=success, steps=steps_taken, score=score, rewards=rewards)
    return success, steps_taken, score, rewards


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    if not API_KEY:
        print("ERROR: HF_TOKEN environment variable is required", flush=True)
        sys.exit(1)

    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    env = ATCEnv()

    successes = 0
    total_score = 0.0

    for task_name in TASKS:
        ok, _steps, score, _rewards = run_episode(env, client, task_name)
        if ok:
            successes += 1
        total_score += score

    avg_score = total_score / len(TASKS) if TASKS else 0.0

    print(f"\n=== SUMMARY ===", flush=True)
    print(f"Tasks completed: {successes}/{len(TASKS)}", flush=True)
    print(f"Average score:   {avg_score:.2f}", flush=True)
    print(f"Total score:     {total_score:.2f}", flush=True)


if __name__ == "__main__":
    main()
