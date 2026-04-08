"""Verbose inference script - shows prompt, server response, and model output."""

import os
import sys
import re
import json
import time
import atexit
import shutil
import subprocess
import urllib.request
import urllib.error
import threading
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from rl_env.environment import ATCEnv
from rl_env.models import ATCAction
from rl_env.prompts.atc_prompt import generate_atc_prompt
from rl_env.parsers import parse, ParseError


TASKS = ["single_approach", "traffic_pattern", "storm_traffic"]
MAX_STEPS_PER_EPISODE = 200
VERBOSE = True
SIM_STEP_SECONDS = 1.0
TARGET_SIM_SPEED = 4.0
REAL_TICK_SECONDS = SIM_STEP_SECONDS / TARGET_SIM_SPEED
MODEL_POLL_INTERVAL_SECONDS = 0.05
MODEL_MAX_IDLE_SIM_TICKS = 60
UI_HEARTBEAT_SECONDS = 3.0
COMMAND_REPEAT_COOLDOWN_SIM_TICKS = 12
MODEL_COMMAND_JSON_KEY = "commands"
QUIET_UI_STACK_LOGS = True
UI_SYNC_URL = os.environ.get("UI_SYNC_URL", "http://localhost:8000/external/state")
API_STATE_URL = os.environ.get("API_STATE_URL", "http://localhost:8000/state")
UI_URL = os.environ.get("UI_URL", "http://localhost:5173")
LAUNCHED_PROCESSES: list[subprocess.Popen] = []
RUN_LOG_HANDLE = None


class _TeeStream:
    def __init__(self, *streams):
        self._streams = streams

    def write(self, data: str):
        for stream in self._streams:
            stream.write(data)
        return len(data)

    def flush(self):
        for stream in self._streams:
            stream.flush()


def _init_run_log() -> Path:
    global RUN_LOG_HANDLE
    log_dir = _repo_root() / "logs" / "verbose_runs"
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"inference_verbose_{timestamp}.log"
    RUN_LOG_HANDLE = open(log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = _TeeStream(sys.stdout, RUN_LOG_HANDLE)
    sys.stderr = _TeeStream(sys.stderr, RUN_LOG_HANDLE)
    return log_path


class GeminiAIStudioClient:
    DEFAULT_MODEL = "gemma-4-26b-a4b-it"
    DEFAULT_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
    RETRY_DELAYS = (1.0, 2.0, 4.0)

    def __init__(
        self,
        api_key: str,
        model_name: Optional[str] = None,
        api_base_url: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self.api_key = api_key
        self.model_name = model_name or os.environ.get(
            "GOOGLE_MODEL_NAME", self.DEFAULT_MODEL
        )
        self.api_base_url = api_base_url or os.environ.get(
            "GOOGLE_API_BASE_URL", self.DEFAULT_API_BASE
        )
        self.timeout = timeout

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        full_prompt = prompt if not system_prompt else f"{system_prompt}\n\n{prompt}"
        url = (
            f"{self.api_base_url}/models/{self.model_name}:generateContent"
            f"?key={self.api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 1024,
            },
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            body = json.loads(response.read().decode("utf-8"))

        candidates = body.get("candidates", [])
        if not candidates:
            prompt_feedback = body.get("promptFeedback")
            raise RuntimeError(
                f"Google AI Studio returned no candidates: {prompt_feedback}"
            )

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts)
        if not text:
            finish_reason = candidates[0].get("finishReason", "unknown")
            raise RuntimeError(f"Google AI Studio returned empty text: {finish_reason}")

        return text

    def generate_with_retry(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_retries: int = 3,
    ) -> str:
        delays = self.RETRY_DELAYS[:max_retries]

        for attempt, delay in enumerate(delays):
            try:
                return self.generate(prompt, system_prompt)
            except urllib.error.HTTPError:
                if attempt < len(delays) - 1:
                    time.sleep(delay)
                else:
                    raise
            except urllib.error.URLError:
                if attempt < len(delays) - 1:
                    time.sleep(delay)
                else:
                    raise

        return self.generate(prompt, system_prompt)


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


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _url_ready(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1.5):
            return True
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def _wait_for_url(url: str, attempts: int = 20, delay: float = 0.5) -> bool:
    for _ in range(attempts):
        if _url_ready(url):
            return True
        time.sleep(delay)
    return False


def _cleanup_launched_processes() -> None:
    for process in reversed(LAUNCHED_PROCESSES):
        if process.poll() is None:
            process.terminate()
    global RUN_LOG_HANDLE
    if RUN_LOG_HANDLE is not None:
        RUN_LOG_HANDLE.flush()
        RUN_LOG_HANDLE.close()
        RUN_LOG_HANDLE = None


atexit.register(_cleanup_launched_processes)


def _ensure_live_ui_stack() -> None:
    repo_root = _repo_root()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root.parent) + os.pathsep + env.get("PYTHONPATH", "")

    if not _url_ready(API_STATE_URL):
        print("🛰️  Starting backend API for live UI sync...")
        backend_log_target = subprocess.DEVNULL if QUIET_UI_STACK_LOGS else None
        backend = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "atc_rl_api.api.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
            ],
            cwd=repo_root,
            env=env,
            stdout=backend_log_target,
            stderr=backend_log_target,
        )
        LAUNCHED_PROCESSES.append(backend)
        if not _wait_for_url(API_STATE_URL):
            raise RuntimeError("Backend API did not start in time")

    if not _url_ready(UI_URL):
        pnpm = shutil.which("pnpm")
        if pnpm is None:
            raise RuntimeError("pnpm is required to auto-launch the visualizer UI")

        print("🖥️  Starting visualizer UI with pnpm...")
        frontend_log_target = subprocess.DEVNULL if QUIET_UI_STACK_LOGS else None
        frontend = subprocess.Popen(
            [pnpm, "run", "dev", "--", "--host", "0.0.0.0"],
            cwd=repo_root / "visualizer",
            env=env,
            stdout=frontend_log_target,
            stderr=frontend_log_target,
        )
        LAUNCHED_PROCESSES.append(frontend)
        if not _wait_for_url(UI_URL):
            raise RuntimeError("Visualizer UI did not start in time")

    print(f"🌐 Live UI ready at {UI_URL}")


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
    clear_engine_events: bool = True,
    include_rl_events: bool = True,
) -> None:
    if env.engine is None:
        return

    state = env.engine.get_full_state(clear_events=clear_engine_events)
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

    raw_engine_events = list(info.get("events", []))
    if not raw_engine_events and clear_engine_events:
        raw_engine_events = list(state.get("events", []))

    custom_events = []
    if include_rl_events:
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

        if action_str:
            custom_events.append(
                {
                    "type": "RL_ACTION",
                    "action": action_str,
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

    state["events"] = custom_events + raw_engine_events
    _post_ui_state(state)


@dataclass
class ModelDecision:
    action: ATCAction
    action_str: str
    prompt: str
    llm_response: str
    error: str
    source_step: int


def _has_meaningful_engine_events(events: list[dict]) -> bool:
    meaningful_event_types = {
        "RUNWAY_CHANGE",
        "SEPARATION_VIOLATION",
        "CRASH",
        "SUCCESSFUL_LANDING",
        "SUCCESSFUL_DEPARTURE",
        "SPAWN",
        "AIRPORT_LOADED",
        "EMERGENCY",
        "GO_AROUND",
    }
    return any(event.get("type") in meaningful_event_types for event in events)


def _normalize_model_response(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return text


def _strip_legacy_response_instructions(prompt: str) -> str:
    marker = "Your response MUST have two sections:"
    if marker in prompt:
        return prompt.split(marker, 1)[0].rstrip()
    return prompt


def _extract_commands_from_json_response(llm_response: str) -> tuple[list[str], str]:
    normalized = _normalize_model_response(llm_response)
    candidates: list[str] = []

    json_block_match = re.search(r"```json\s*(\{.*?\})\s*```", llm_response, re.IGNORECASE | re.DOTALL)
    if json_block_match:
        candidates.append(json_block_match.group(1).strip())

    object_candidates = re.findall(r"\{.*?\}", normalized, re.DOTALL)
    for candidate in reversed(object_candidates):
        stripped = candidate.strip()
        if stripped:
            candidates.append(stripped)

    if normalized.startswith("{") and normalized.endswith("}"):
        candidates.append(normalized)

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue

        raw_commands = payload.get(MODEL_COMMAND_JSON_KEY)
        if not isinstance(raw_commands, list):
            continue

        commands: list[str] = []
        for item in raw_commands:
            if isinstance(item, str):
                command_text = item.strip()
                if command_text:
                    commands.append(command_text)
        return commands, "none"

    return [], "missing_or_invalid_json_commands"


def _build_decision_signature(observation) -> tuple:
    altitude_error_threshold_feet = 1000
    heading_error_threshold_deg = 20
    speed_error_threshold_kts = 20

    def needs_intervention(aircraft) -> bool:
        altitude_error = abs(
            aircraft.position.altitude - aircraft.position.target_altitude
        )
        heading_error = abs(
            (aircraft.motion.heading - aircraft.motion.target_heading + 180.0) % 360.0
            - 180.0
        )
        speed_error = abs(aircraft.motion.speed - aircraft.motion.target_speed)
        return (
            altitude_error > altitude_error_threshold_feet
            or heading_error > heading_error_threshold_deg
            or speed_error > speed_error_threshold_kts
        )

    aircraft_signature = []
    for aircraft in sorted(observation.aircraft, key=lambda ac: ac.callsign):
        aircraft_signature.append(
            (
                aircraft.callsign,
                aircraft.intent.state,
                needs_intervention(aircraft),
                aircraft.separation.conflict_risk,
                tuple(sorted(aircraft.alerts)),
            )
        )

    return (
        tuple(observation.airport_status.active_runways),
        len(observation.aircraft),
        tuple(aircraft_signature),
    )


def _augment_prompt_for_json_commands(base_prompt: str) -> str:
    base_prompt = _strip_legacy_response_instructions(base_prompt)
    json_contract = (
        "\n\nSTRICT OUTPUT FORMAT (REQUIRED):\n"
        "Return ONLY valid JSON with no markdown fences and no extra prose.\n"
        'Use exactly this schema: {"commands":["ATC ...","ATC ..."]}\n'
        'If no action is needed, return {"commands":[]}.'
    )
    return base_prompt + json_contract


def _parse_action_from_response(llm_response: str) -> tuple[ATCAction, str, str]:
    raw_commands, extract_error = _extract_commands_from_json_response(llm_response)
    if extract_error != "none":
        # Safety-first: never infer commands from chain-of-thought prose.
        return ATCAction(commands=[]), "", f"parse_error:{extract_error}"

    commands: list[str] = []
    try:
        for command_text in raw_commands:
            parsed = parse(command_text)
            parsed_commands = parsed if isinstance(parsed, list) else [parsed]
            for cmd in parsed_commands:
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

        # Preserve order while removing duplicates.
        commands = list(dict.fromkeys(commands))
        if not commands:
            return ATCAction(commands=[]), "", "none"

        return ATCAction(commands=commands), " ".join(commands), "none"
    except ParseError as e:
        return ATCAction(commands=[]), "", f"parse_error:{e}"


def _format_commands_for_log(llm_response: str) -> list[str]:
    raw_commands, _ = _extract_commands_from_json_response(llm_response)
    parsed_commands = []
    for command_text in raw_commands:
        try:
            parsed = parse(command_text)
        except ParseError:
            continue
        for cmd in (parsed if isinstance(parsed, list) else [parsed]):
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
            parsed_commands.append(cmd_str)
    return list(dict.fromkeys(parsed_commands))


def run_episode(
    env: ATCEnv,
    client: GeminiAIStudioClient,
    task_name: str,
    model_name: str,
) -> tuple[bool, int, float, list[float]]:
    observation, info = env.reset(task=task_name)
    if env.engine is not None:
        env.engine.time_scale = 4.0
    if observation.aircraft:
        spawn_summary = ", ".join(
            f"{ac.callsign}:{ac.position.segment}@{ac.position.altitude}ft"
            for ac in observation.aircraft
        )
        print(f"🛫 Initial spawn set ({len(observation.aircraft)}): {spawn_summary}")
    episode_rewards: list[float] = []
    rl_step_count = 0
    sim_tick_count = 0
    success = False
    terminal_reason = "not_terminated"
    latest_observation = observation
    pending_decision: Optional[ModelDecision] = None
    shared_lock = threading.Lock()
    stop_event = threading.Event()
    decision_request_event = threading.Event()
    simulation_error: Optional[str] = None
    model_in_flight = False
    model_trigger_tick = 0
    model_trigger_reason = "episode_start"
    last_model_request_tick = -1
    last_decision_signature = _build_decision_signature(observation)
    last_applied_action = ""
    last_applied_action_tick = -999999

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
        include_rl_events=False,
    )

    print(f"\n{'=' * 60}")
    print(f"[START] task={task_name} env=ATCEnv-v1 model={model_name}")
    print(f"{'=' * 60}\n")

    def simulation_loop() -> None:
        nonlocal rl_step_count
        nonlocal sim_tick_count
        nonlocal latest_observation
        nonlocal pending_decision
        nonlocal success
        nonlocal simulation_error
        nonlocal model_trigger_tick
        nonlocal model_trigger_reason
        nonlocal last_model_request_tick
        nonlocal model_in_flight
        nonlocal last_decision_signature
        nonlocal last_applied_action
        nonlocal last_applied_action_tick
        nonlocal terminal_reason
        cumulative_reward = 0.0
        next_tick = time.monotonic()
        last_ui_publish_time = time.monotonic()

        while not stop_event.is_set():
            with shared_lock:
                decision = pending_decision
                if decision:
                    pending_decision = None

            try:
                if decision is None:
                    env.engine.step(SIM_STEP_SECONDS)
                    sim_tick_count += 1
                    reward = 0.0
                    done = False
                    info_step = {"events": list(env.engine.event_buffer), "reward_breakdown": {}}
                    with shared_lock:
                        latest_observation = env._build_observation()
                        observation_step = latest_observation
                    done = env._check_terminal_conditions(observation_step)
                    current_signature = _build_decision_signature(observation_step)

                    now = time.monotonic()
                    should_publish_ui = (
                        done
                        or _has_meaningful_engine_events(info_step["events"])
                        or (now - last_ui_publish_time >= UI_HEARTBEAT_SECONDS)
                    )
                    if should_publish_ui:
                        _publish_ui_state(
                            env=env,
                            task_name=task_name,
                            model_name=model_name,
                            step=rl_step_count,
                            reward=0.0,
                            cumulative_reward=cumulative_reward,
                            done=done,
                            info=info_step,
                            phase="sim_tick",
                            include_rl_events=False,
                        )
                        last_ui_publish_time = now

                    should_trigger_model = False
                    with shared_lock:
                        idle_ticks = sim_tick_count - last_model_request_tick
                        signature_changed = current_signature != last_decision_signature
                        if (
                            pending_decision is None
                            and not model_in_flight
                            and (
                                _has_meaningful_engine_events(info_step["events"])
                                or signature_changed
                                or idle_ticks >= MODEL_MAX_IDLE_SIM_TICKS
                            )
                        ):
                            last_decision_signature = current_signature
                            model_trigger_tick = sim_tick_count
                            model_trigger_reason = (
                                "engine_event"
                                if _has_meaningful_engine_events(info_step["events"])
                                else "state_change"
                                if signature_changed
                                else "idle_fallback"
                            )
                            should_trigger_model = True
                    if should_trigger_model:
                        decision_request_event.set()
                else:
                    action = decision.action
                    action_str = decision.action_str
                    prompt = decision.prompt
                    llm_response = decision.llm_response
                    error = decision.error
                    observation_step, reward, done, _, info_step = env.step(action)
                    episode_rewards.append(reward)
                    cumulative_reward += reward
                    rl_step_count += 1

                    with shared_lock:
                        latest_observation = observation_step

                    _publish_ui_state(
                        env=env,
                        task_name=task_name,
                        model_name=model_name,
                        step=rl_step_count,
                        reward=reward,
                        cumulative_reward=cumulative_reward,
                        done=done,
                        info=info_step,
                        prompt=prompt,
                        llm_response=llm_response,
                        action_str=action_str,
                        error=error,
                    )
                    last_ui_publish_time = time.monotonic()
                    if action_str:
                        last_applied_action = action_str
                        last_applied_action_tick = sim_tick_count

                    print(
                        f'\n[RL_STEP] step={rl_step_count} action="{action_str or "(no commands)"}" reward={reward:.4f} done={done} error={error}'
                    )

                    decision_age_steps = sim_tick_count - decision.source_step
                    if decision_age_steps > 0 and VERBOSE:
                        print(
                            f"⏱️  Applied model output after {decision_age_steps} simulation tick(s)"
                        )

                    if VERBOSE:
                        print(f"\n📊 REWARD: {reward:.4f}")
                        print(f"📊 CUMULATIVE REWARD: {cumulative_reward:.4f}")
                        print(f"📊 DONE: {done}")
            except Exception as e:
                simulation_error = f"step_error:{e}"
                stop_event.set()
                print(
                    f'\n[SIM] tick={sim_tick_count + 1} error={simulation_error}'
                )
                break

            if done:
                success = True
                terminal_reason = env._get_terminal_event()
                stop_event.set()
                break

            if rl_step_count >= MAX_STEPS_PER_EPISODE:
                stop_event.set()
                break

            next_tick += REAL_TICK_SECONDS
            sleep_for = next_tick - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                next_tick = time.monotonic()

    sim_thread = threading.Thread(target=simulation_loop, daemon=True)
    sim_thread.start()

    decision_request_event.set()
    model_last_handled_tick = -1
    while not stop_event.is_set():
        if not decision_request_event.wait(timeout=MODEL_POLL_INTERVAL_SECONDS):
            continue

        with shared_lock:
            current_tick = model_trigger_tick
            current_rl_step = rl_step_count
            observation_for_model = latest_observation
            trigger_reason = model_trigger_reason
            last_action = last_applied_action
            last_action_tick = last_applied_action_tick
            if (
                model_in_flight
                or current_tick == model_last_handled_tick
                or current_rl_step >= MAX_STEPS_PER_EPISODE
            ):
                decision_request_event.clear()
                if current_rl_step >= MAX_STEPS_PER_EPISODE:
                    stop_event.set()
                continue
            model_in_flight = True
            last_model_request_tick = current_tick
            model_last_handled_tick = current_tick
            decision_request_event.clear()

        prompt = ""
        llm_response = ""
        decision_error = "none"

        try:
            prompt = _augment_prompt_for_json_commands(
                generate_atc_prompt(observation_for_model)
            )
            llm_response = client.generate_with_retry(prompt)

            if VERBOSE:
                print(f"\n{'─' * 60}")
                print(
                    f"MODEL CYCLE @ SIM_TICK {current_tick} RL_STEP {current_rl_step} trigger={trigger_reason}"
                )
                print(f"{'─' * 60}")
                print(f"\n📤 PROMPT SENT TO MODEL:\n")
                print(prompt)
                print(f"\n{'─' * 60}")
                print(f"📥 MODEL RESPONSE:\n")

                structured_matches = _format_commands_for_log(llm_response)
                print(f"💭 THINKING:\n{llm_response}")
                print(f"\n{'─' * 60}")
                if structured_matches:
                    print(f"🎯 EXTRACTED COMMANDS: {structured_matches}")
                else:
                    print("⚠️  NO COMMANDS DETECTED IN JSON RESPONSE")
                print(f"\n{'─' * 60}")

            parsed_action, action_str, parse_error = _parse_action_from_response(llm_response)
            decision_error = parse_error

            if (
                parse_error == "none"
                and action_str
                and action_str == last_action
                and (current_tick - last_action_tick) < COMMAND_REPEAT_COOLDOWN_SIM_TICKS
            ):
                parsed_action = ATCAction(commands=[])
                action_str = ""
                decision_error = "suppressed_duplicate_command"

            if VERBOSE:
                if decision_error == "suppressed_duplicate_command":
                    print(
                        f"\n⏭️  SUPPRESSED duplicate command within {COMMAND_REPEAT_COOLDOWN_SIM_TICKS} sim ticks"
                    )
                elif parse_error == "none":
                    print(f"\n✅ PARSED COMMANDS: {parsed_action.commands}")
                else:
                    print(f"\n❌ PARSE ERROR: {parse_error}")

        except Exception as e:
            parsed_action = ATCAction(commands=[])
            action_str = ""
            decision_error = f"llm_error:{e}"
            if VERBOSE:
                print(f"\n❌ LLM ERROR: {e}")

        if stop_event.is_set():
            with shared_lock:
                model_in_flight = False
            break

        with shared_lock:
            pending_decision = ModelDecision(
                action=parsed_action,
                action_str=action_str,
                prompt=prompt,
                llm_response=llm_response,
                error=decision_error,
                source_step=current_tick,
            )
            model_in_flight = False

    sim_thread.join()

    if simulation_error:
        print(f"\n❌ SIMULATION LOOP ERROR: {simulation_error}")

    score = sum(episode_rewards)

    _publish_ui_state(
        env=env,
        task_name=task_name,
        model_name=model_name,
        step=rl_step_count,
        reward=episode_rewards[-1] if episode_rewards else 0.0,
        cumulative_reward=score,
        done=success,
        info={"events": []},
        phase="end",
        include_rl_events=False,
    )

    print(f"\n{'=' * 60}")
    print(
        f"[END] success={success} rl_steps={rl_step_count} sim_ticks={sim_tick_count} score={score:.4f} terminal_reason={terminal_reason}"
    )
    print(f"{'=' * 60}\n")

    return success, rl_step_count, score, episode_rewards


def main():
    log_path = _init_run_log()
    google_api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get(
        "GEMINI_API_KEY"
    )
    if not google_api_key:
        print("ERROR: GOOGLE_API_KEY environment variable is required")
        sys.exit(1)

    api_base_url = os.environ.get(
        "GOOGLE_API_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
    )
    model_name = os.environ.get("GOOGLE_MODEL_NAME", GeminiAIStudioClient.DEFAULT_MODEL)

    print(f"\n🚀 Initializing LLM Client")
    print(f"   Provider: Google AI Studio")
    print(f"   API: {api_base_url}")
    print(f"   Model: {model_name}")
    print(f"   Log File: {log_path}")

    _ensure_live_ui_stack()

    client = GeminiAIStudioClient(
        api_key=google_api_key,
        model_name=model_name,
        api_base_url=api_base_url,
    )

    print(f"✅ Client initialized\n")

    env = ATCEnv(airport_code="VOCB")
    print("⚡ Verbose inference will run simulation at 4x speed")

    total_success = 0
    total_steps = 0
    total_score = 0.0

    tasks_to_run = TASKS[1:]
    print(f"⏭️  Skipping first episode for now. Running tasks: {tasks_to_run}")

    for task in tasks_to_run:
        success, steps, score, _ = run_episode(env, client, task, model_name)
        if success:
            total_success += 1
        total_steps += steps
        total_score += score

    print(f"\n{'=' * 60}")
    print(f"📋 SUMMARY")
    print(f"{'=' * 60}")
    print(f"Tasks completed: {total_success}/{len(tasks_to_run)}")
    print(f"Total steps: {total_steps}")
    print(f"Total score: {total_score:.4f}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
