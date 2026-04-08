"""Verbose inference script - shows prompt, server response, and model output."""

import os
import sys
import re
import json
import time
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv()

from rl_env.client import LLMClient
from rl_env.environment import ATCEnv
from rl_env.models import ATCAction
from rl_env.prompts.atc_prompt import generate_atc_prompt
from rl_env.parsers import parse, ParseError


TASKS = ["single_approach", "traffic_pattern", "storm_traffic"]
MAX_STEPS_PER_EPISODE = 200
VERBOSE = True
UI_SYNC_URL = os.environ.get("UI_SYNC_URL", "http://localhost:8000/external/state")


def _preview(text: str, limit: int = 240) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}…"


def _post_ui_state(payload: dict) -> None:
    try:
        req = urllib.request.Request(
            UI_SYNC_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=1.5):
            pass
    except (urllib.error.URLError, TimeoutError, ValueError):
        pass


def _publish_ui_state(
    env: ATCEnv,
    task_name: str,
    model_name: str,
    step: int,
    reward: float,
    cumulative_reward: float,
    done: bool,
    info: dict,
    prompt: str = "",
    llm_response: str = "",
    action_str: str = "",
    error: str = "none",
    phase: str = "step",
) -> None:
    if env.engine is None:
        return

    state = env.engine.get_full_state(clear_events=False)
    state.update(
        {
            "source": "rl_env_inference",
            "current_task": task_name,
            "model_name": model_name,
            "step": step,
            "reward": round(reward, 4),
            "cumulative_reward": round(cumulative_reward, 4),
            "done": done,
            "reward_breakdown": info.get("reward_breakdown", {}),
        }
    )

    timestamp = time.time()
    custom_events = [
        {
            "type": "RL_TASK",
            "task": task_name,
            "model": model_name,
            "phase": phase,
            "step": step,
            "timestamp": timestamp,
        }
    ]

    if prompt:
        custom_events.append(
            {
                "type": "RL_PROMPT",
                "msg": _preview(prompt),
                "step": step,
                "timestamp": timestamp,
            }
        )

    if llm_response:
        custom_events.append(
            {
                "type": "RL_RESPONSE",
                "msg": _preview(llm_response),
                "step": step,
                "timestamp": timestamp,
            }
        )

    if action_str or phase == "step":
        custom_events.append(
            {
                "type": "RL_ACTION",
                "action": action_str or "(no commands)",
                "step": step,
                "timestamp": timestamp,
            }
        )

    if error != "none":
        custom_events.append(
            {
                "type": "RL_ERROR",
                "msg": error,
                "step": step,
                "timestamp": timestamp,
            }
        )

    custom_events.append(
        {
            "type": "RL_REWARD",
            "reward": round(reward, 4),
            "cumulative_reward": round(cumulative_reward, 4),
            "done": done,
            "step": step,
            "timestamp": timestamp,
        }
    )

    state["events"] = custom_events + list(info.get("events", []))
    _post_ui_state(state)


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

    _publish_ui_state(
        env=env,
        task_name=task_name,
        model_name=model_name,
        step=0,
        reward=0.0,
        cumulative_reward=0.0,
        done=False,
        info=info,
        phase="start",
    )

    print(f"\n{'=' * 60}")
    print(f"[START] task={task_name} env=ATCEnv-v1 model={model_name}")
    print(f"{'=' * 60}\n")

    while step < MAX_STEPS_PER_EPISODE:
        step += 1
        action_str = ""
        reward = 0.0
        done = False
        error = "none"
        prompt = ""
        llm_response = ""

        try:
            prompt = generate_atc_prompt(observation)
            llm_response = client.generate_with_retry(prompt)

            if VERBOSE:
                print(f"\n{'─' * 60}")
                print(f"STEP {step}")
                print(f"{'─' * 60}")
                print(f"\n📤 PROMPT SENT TO MODEL:\n")
                print(prompt)
                print(f"\n{'─' * 60}")
                print(f"📥 MODEL RESPONSE:\n")

                # Extract commands using regex
                cmd_pattern = r"ATC\s+\w+\s+\w+(?:\s+\S+)?"
                matches = re.findall(cmd_pattern, llm_response, re.IGNORECASE)

                if matches:
                    # Show thinking with commands highlighted
                    thinking_only = llm_response
                    for cmd in matches:
                        thinking_only = thinking_only.replace(cmd, f"[{cmd}]")
                    print(f"💭 THINKING (commands highlighted):\n{thinking_only}")
                    print(f"\n{'─' * 60}")
                    print(f"🎯 EXTRACTED COMMANDS: {matches}")
                else:
                    print(f"💭 THINKING:\n{llm_response}")
                    print(f"\n{'─' * 60}")
                    print("⚠️  NO COMMANDS DETECTED IN RESPONSE")

                print(f"\n{'─' * 60}")

            # Extract commands portion for parsing
            commands_text = llm_response
            if "COMMANDS:" in llm_response.upper():
                parts = llm_response.upper().split("COMMANDS:")
                if len(parts) > 1:
                    commands_text = parts[1].strip()

            # Parse commands
            commands = []
            try:
                parsed = parse(commands_text)
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
                    print(f"\n✅ PARSED COMMANDS: {commands}")

            except ParseError as e:
                error = f"parse_error:{e}"
                action = ATCAction(commands=[])
                if VERBOSE:
                    print(f"\n❌ PARSE ERROR: {e}")

        except Exception as e:
            error = f"llm_error:{e}"
            action = ATCAction(commands=[])
            if VERBOSE:
                print(f"\n❌ LLM ERROR: {e}")

        try:
            observation, reward, done, _, info = env.step(action)
            episode_rewards.append(reward)
            cumulative_reward = sum(episode_rewards)

            _publish_ui_state(
                env=env,
                task_name=task_name,
                model_name=model_name,
                step=step,
                reward=reward,
                cumulative_reward=cumulative_reward,
                done=done,
                info=info,
                prompt=prompt,
                llm_response=llm_response,
                action_str=action_str,
                error=error,
            )

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

    _publish_ui_state(
        env=env,
        task_name=task_name,
        model_name=model_name,
        step=step,
        reward=episode_rewards[-1] if episode_rewards else 0.0,
        cumulative_reward=score,
        done=success,
        info={"events": []},
        action_str="episode complete",
        phase="end",
    )

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

    env = ATCEnv(airport_code="VOCB")

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
