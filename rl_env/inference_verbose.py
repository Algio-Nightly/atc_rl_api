"""Verbose inference script - shows prompt, server response, and model output."""

import os
import sys

from rl_env.client import LLMClient
from rl_env.environment import ATCEnv
from rl_env.models import ATCAction
from rl_env.prompts.atc_prompt import generate_atc_prompt
from rl_env.parsers import parse, ParseError


TASKS = ["single_approach", "traffic_pattern", "storm_traffic"]
MAX_STEPS_PER_EPISODE = 200
VERBOSE = True


def run_episode(
    env: ATCEnv,
    client: LLMClient,
    task_name: str,
    model_name: str,
) -> tuple[bool, int, float, list[float]]:
    observation, info = env.reset(task=task_name)
    episode_rewards: list[float] = []
    step = 0
    success = False

    print(f"\n{'=' * 60}")
    print(f"[START] task={task_name} env=ATCEnv-v1 model={model_name}")
    print(f"{'=' * 60}\n")

    while step < MAX_STEPS_PER_EPISODE:
        step += 1
        action_str = ""
        reward = 0.0
        done = False
        error = "none"

        try:
            prompt = generate_atc_prompt(observation)

            if VERBOSE:
                print(f"\n{'─' * 60}")
                print(f"STEP {step}")
                print(f"{'─' * 60}")
                print(f"\n📤 PROMPT SENT TO MODEL:\n")
                print(prompt)
                print(f"\n{'─' * 60}")

            llm_response = client.generate_with_retry(prompt)

            if VERBOSE:
                print(f"📥 MODEL RESPONSE:\n")
                print(llm_response)
                print(f"\n{'─' * 60}")

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

                if VERBOSE:
                    print(f"✅ PARSED COMMANDS: {commands}")

            except ParseError as e:
                error = f"parse_error:{e}"
                action = ATCAction(commands=[])
                if VERBOSE:
                    print(f"❌ PARSE ERROR: {e}")

        except Exception as e:
            error = f"llm_error:{e}"
            action = ATCAction(commands=[])
            if VERBOSE:
                print(f"❌ LLM ERROR: {e}")

        try:
            observation, reward, done, _, info = env.step(action)
            episode_rewards.append(reward)

            if action_str:
                print(
                    f'\n[STEP] step={step} action="{action_str}" reward={reward:.4f} done={done} error={error}'
                )
            else:
                print(
                    f'\n[STEP] step={step} action="" reward={reward:.4f} done={done} error={error}'
                )

            if VERBOSE:
                print(f"\n📊 REWARD: {reward:.4f}")
                print(f"📊 CUMULATIVE REWARD: {sum(episode_rewards):.4f}")
                print(f"📊 DONE: {done}")

            if done:
                success = True
                break

        except Exception as e:
            error = f"step_error:{e}"
            print(
                f'\n[STEP] step={step} action="{action_str}" reward={reward} done=true error={error}'
            )
            break

    score = sum(episode_rewards)
    print(f"\n{'=' * 60}")
    print(f"[END] success={success} steps={step} score={score:.4f}")
    print(f"{'=' * 60}\n")

    return success, step, score, episode_rewards


def main():
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        print("ERROR: HF_TOKEN environment variable is required")
        sys.exit(1)

    api_base_url = os.environ.get("API_BASE_URL")
    model_name = os.environ.get("MODEL_NAME", "meta-llama/Llama-3.3-70B-Instruct")

    print(f"\n🚀 Initializing LLM Client")
    print(f"   API: {api_base_url or 'default'}")
    print(f"   Model: {model_name}")

    client = LLMClient(
        api_base_url=api_base_url,
        model_name=model_name,
        hf_token=hf_token,
    )

    print(f"✅ Client initialized\n")

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

    print(f"\n{'=' * 60}")
    print(f"📋 SUMMARY")
    print(f"{'=' * 60}")
    print(f"Tasks completed: {total_success}/{len(TASKS)}")
    print(f"Total steps: {total_steps}")
    print(f"Total score: {total_score:.4f}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
