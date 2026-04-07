"""Competition baseline inference script for ATC RL environment."""

import os
import sys
from typing import Optional

from rl_env.client import LLMClient
from rl_env.environment import ATCEnv
from rl_env.models import ATCAction
from rl_env.prompts.atc_prompt import generate_atc_prompt
from rl_env.parsers import parse, ParseError


TASKS = ["single_approach", "traffic_pattern", "storm_traffic"]

MAX_STEPS_PER_EPISODE = 200


def run_episode(
    env: ATCEnv,
    client: LLMClient,
    task_name: str,
    model_name: str,
) -> tuple[bool, int, float, list[float]]:
    """
    Run a single episode for a given task.

    Args:
        env: ATC environment instance
        client: LLM client instance
        task_name: Name of the task to run
        model_name: Model name for logging

    Returns:
        Tuple of (success, steps, score, rewards_list)
    """
    observation, info = env.reset(task=task_name)
    episode_rewards: list[float] = []
    step = 0
    success = False

    print(f"[START] task={task_name} env=ATCEnv-v1 model={model_name}")

    while step < MAX_STEPS_PER_EPISODE:
        step += 1
        action_str = ""
        reward = 0.0
        done = False
        error = "none"

        try:
            prompt = generate_atc_prompt(observation)
            llm_response = client.generate_with_retry(prompt)

            commands = []
            try:
                parsed = parse(llm_response)
                if isinstance(parsed, list):
                    for cmd in parsed:
                        cmd_str = f"ATC {cmd['command']} {cmd['callsign']}"
                        if "heading" in cmd:
                            cmd_str += f" {cmd['heading']}"
                        elif "altitude" in cmd:
                            cmd_str += f" {cmd['altitude']}"
                        elif "speed" in cmd:
                            cmd_str += f" {cmd['speed']}"
                        elif "waypoint" in cmd:
                            cmd_str += f" {cmd['waypoint']}"
                        elif "runway" in cmd:
                            cmd_str += f" {cmd['runway']}"
                        commands.append(cmd_str)
                else:
                    cmd = parsed
                    cmd_str = f"ATC {cmd['command']} {cmd['callsign']}"
                    if "heading" in cmd:
                        cmd_str += f" {cmd['heading']}"
                    elif "altitude" in cmd:
                        cmd_str += f" {cmd['altitude']}"
                    elif "speed" in cmd:
                        cmd_str += f" {cmd['speed']}"
                    elif "waypoint" in cmd:
                        cmd_str += f" {cmd['waypoint']}"
                    elif "runway" in cmd:
                        cmd_str += f" {cmd['runway']}"
                    commands.append(cmd_str)

                action_str = " ".join(commands) if commands else ""
                action = ATCAction(commands=commands)

            except ParseError as e:
                error = f"parse_error:{e}"
                action = ATCAction(commands=[])

        except Exception as e:
            error = f"llm_error:{e}"
            action = ATCAction(commands=[])

        try:
            observation, reward, done, _, info = env.step(action)
            episode_rewards.append(reward)

            if action_str:
                print(
                    f'[STEP] step={step} action="{action_str}" reward={reward} done={done} error={error}'
                )
            else:
                print(
                    f'[STEP] step={step} action="" reward={reward} done={done} error={error}'
                )

            if done:
                success = True
                break

        except Exception as e:
            error = f"step_error:{e}"
            print(
                f'[STEP] step={step} action="{action_str}" reward={reward} done=true error={error}'
            )
            break

    score = sum(episode_rewards)
    print(
        f"[END] success={success} steps={step} score={score} rewards={episode_rewards}"
    )

    return success, step, score, episode_rewards


def main():
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        print("ERROR: HF_TOKEN environment variable is required")
        sys.exit(1)

    api_base_url = os.environ.get("API_BASE_URL")
    model_name = os.environ.get("MODEL_NAME", "meta-llama/Llama-3.3-70B-Instruct")

    client = LLMClient(
        api_base_url=api_base_url,
        model_name=model_name,
        hf_token=hf_token,
    )

    env = ATCEnv()

    total_success = 0
    total_steps = 0
    total_score = 0.0

    for task in TASKS:
        success, steps, score, _ = run_episode(env, client, task, model_name)
        if success:
            total_success += 1
        total_steps += steps
        total_score += score

    print(f"\n=== SUMMARY ===")
    print(f"Tasks completed: {total_success}/{len(TASKS)}")
    print(f"Total steps: {total_steps}")
    print(f"Total score: {total_score}")


if __name__ == "__main__":
    main()
