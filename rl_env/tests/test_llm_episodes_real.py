"""Real LLM episode tests - requires HF_TOKEN environment variable."""

import os
import pytest

from rl_env.environment import ATCEnv
from rl_env.client import LLMClient
from rl_env.prompts.atc_prompt import generate_atc_prompt
from rl_env.parsers import parse, ParseError
from rl_env.models import ATCAction


pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("HF_TOKEN"),
        reason="HF_TOKEN environment variable not set",
    ),
    pytest.mark.slow,
    pytest.mark.llm,
]


@pytest.fixture
def llm_client():
    return LLMClient(hf_token=os.environ.get("HF_TOKEN"))


@pytest.fixture
def llm_client_with_retry():
    return LLMClient(hf_token=os.environ.get("HF_TOKEN"))


def _run_llm_episode(env: ATCEnv, client: LLMClient, max_steps: int = 100) -> tuple:
    observation, info = env.reset()
    cumulative_reward = 0.0
    terminal_event = None
    success = False

    for step in range(max_steps):
        prompt = generate_atc_prompt(observation)

        try:
            llm_response = client.generate_with_retry(prompt)
        except Exception:
            action = ATCAction(commands=[])
        else:
            try:
                parsed = parse(llm_response)
                commands = []

                if isinstance(parsed, list):
                    for cmd in parsed:
                        cmd_str = _build_command_string(cmd)
                        if cmd_str:
                            commands.append(cmd_str)
                else:
                    cmd_str = _build_command_string(parsed)
                    if cmd_str:
                        commands.append(cmd_str)

                action = ATCAction(commands=commands)

            except ParseError:
                action = ATCAction(commands=[])

        observation, reward, success, _, info = env.step(action)
        cumulative_reward += reward

        if success:
            terminal_event = info.get("terminal_event")
            break

    return (
        success,
        env.step_count,
        cumulative_reward,
        terminal_event,
        info,
    )


def _build_command_string(cmd: dict) -> str:
    command = cmd.get("command", "").upper()
    callsign = cmd.get("callsign", "").upper()

    if not command or not callsign:
        return ""

    cmd_str = f"ATC {command} {callsign}"

    for key in ["heading", "altitude", "speed", "waypoint", "runway"]:
        if key in cmd and cmd[key] is not None:
            cmd_str += f" {cmd[key]}"

    return cmd_str


class TestLLMSingleAircraftLanding:
    def test_llm_single_aircraft_landing(self, llm_client_with_retry):
        env = ATCEnv()
        max_steps = 150

        observation, info = env.reset(task="single_approach")
        initial_aircraft_count = len(observation.aircraft)

        assert initial_aircraft_count >= 1, "Should have at least one aircraft"

        cumulative_reward = 0.0

        for step in range(max_steps):
            prompt = generate_atc_prompt(observation)

            try:
                llm_response = llm_client_with_retry.generate_with_retry(prompt)
            except Exception:
                action = ATCAction(commands=[])
            else:
                try:
                    parsed = parse(llm_response)
                    commands = []

                    if isinstance(parsed, list):
                        for cmd in parsed:
                            cmd_str = _build_command_string(cmd)
                            if cmd_str:
                                commands.append(cmd_str)
                    else:
                        cmd_str = _build_command_string(parsed)
                        if cmd_str:
                            commands.append(cmd_str)

                    action = ATCAction(commands=commands)
                except ParseError:
                    action = ATCAction(commands=[])

            observation, reward, done, _, info = env.step(action)
            cumulative_reward += reward

            if done:
                break

        terminal_event = info.get("terminal_event")
        assert terminal_event in [
            "ALL_AIRCRAFT_HANDLED",
            "ENGINE_TERMINAL",
            "LANDING_COMPLETE",
        ], f"Unexpected terminal event: {terminal_event}"

        assert cumulative_reward > 0


class TestLLMMultiAircraftSeparation:
    def test_llm_multi_aircraft_separation(self, llm_client_with_retry):
        env = ATCEnv()
        max_steps = 150

        observation, info = env.reset(task="traffic_pattern")
        initial_aircraft_count = len(observation.aircraft)

        assert initial_aircraft_count >= 2, "Should have at least two aircraft"

        cumulative_reward = 0.0
        no_separation_violation = True

        for step in range(max_steps):
            prompt = generate_atc_prompt(observation)

            try:
                llm_response = llm_client_with_retry.generate_with_retry(prompt)
            except Exception:
                action = ATCAction(commands=[])
            else:
                try:
                    parsed = parse(llm_response)
                    commands = []

                    if isinstance(parsed, list):
                        for cmd in parsed:
                            cmd_str = _build_command_string(cmd)
                            if cmd_str:
                                commands.append(cmd_str)
                    else:
                        cmd_str = _build_command_string(parsed)
                        if cmd_str:
                            commands.append(cmd_str)

                    action = ATCAction(commands=commands)
                except ParseError:
                    action = ATCAction(commands=[])

            observation, reward, done, _, info = env.step(action)
            cumulative_reward += reward

            for ac in observation.aircraft:
                if ac.separation.conflict_risk == "high":
                    no_separation_violation = False

            if done:
                break

        assert no_separation_violation

        terminal_event = info.get("terminal_event")
        assert terminal_event in [
            "ALL_AIRCRAFT_HANDLED",
            "ENGINE_TERMINAL",
        ], f"Unexpected terminal event: {terminal_event}"


class TestLLMGoAroundHandling:
    def test_llm_go_around_handling(self, llm_client_with_retry):
        env = ATCEnv()
        max_steps = 200

        observation, info = env.reset(task="traffic_pattern")

        cumulative_reward = 0.0
        go_around_executed = False

        for step in range(max_steps):
            prompt = generate_atc_prompt(observation)

            try:
                llm_response = llm_client_with_retry.generate_with_retry(prompt)
            except Exception:
                action = ATCAction(commands=[])
            else:
                try:
                    parsed = parse(llm_response)
                    commands = []

                    if isinstance(parsed, list):
                        for cmd in parsed:
                            cmd_str = _build_command_string(cmd)
                            if cmd_str:
                                commands.append(cmd_str)
                    else:
                        cmd_str = _build_command_string(parsed)
                        if cmd_str:
                            commands.append(cmd_str)

                    for cmd_str in commands:
                        if "GO_AROUND" in cmd_str.upper():
                            go_around_executed = True

                    action = ATCAction(commands=commands)
                except ParseError:
                    action = ATCAction(commands=[])

            observation, reward, done, _, info = env.step(action)
            cumulative_reward += reward

            if done:
                break

        terminal_event = info.get("terminal_event")
        assert terminal_event in [
            "ALL_AIRCRAFT_HANDLED",
            "ENGINE_TERMINAL",
            "GO_AROUND_COMPLETE",
        ], f"Unexpected terminal event: {terminal_event}"

        assert env.step_count > 0


class TestLLMRunwaySequencing:
    def test_llm_runway_sequencing(self, llm_client_with_retry):
        env = ATCEnv()
        max_steps = 200

        observation, info = env.reset(task="traffic_pattern")
        initial_aircraft_count = len(observation.aircraft)

        assert initial_aircraft_count >= 2, (
            "Should have multiple aircraft for sequencing"
        )

        cumulative_reward = 0.0
        land_commands_issued = 0

        for step in range(max_steps):
            prompt = generate_atc_prompt(observation)

            try:
                llm_response = llm_client_with_retry.generate_with_retry(prompt)
            except Exception:
                action = ATCAction(commands=[])
            else:
                try:
                    parsed = parse(llm_response)
                    commands = []

                    if isinstance(parsed, list):
                        for cmd in parsed:
                            cmd_str = _build_command_string(cmd)
                            if cmd_str:
                                commands.append(cmd_str)
                    else:
                        cmd_str = _build_command_string(parsed)
                        if cmd_str:
                            commands.append(cmd_str)

                    for cmd_str in commands:
                        if "LAND" in cmd_str.upper():
                            land_commands_issued += 1

                    action = ATCAction(commands=commands)
                except ParseError:
                    action = ATCAction(commands=[])

            observation, reward, done, _, info = env.step(action)
            cumulative_reward += reward

            if done:
                break

        assert land_commands_issued > 0

        terminal_event = info.get("terminal_event")
        assert terminal_event in [
            "ALL_AIRCRAFT_HANDLED",
            "ENGINE_TERMINAL",
        ], f"Unexpected terminal event: {terminal_event}"


class TestLLMEpisodeIntegration:
    def test_llm_episode_single_approach_integration(self, llm_client):
        env = ATCEnv()
        client = llm_client

        success, steps, score, terminal_event, info = _run_llm_episode(
            env, client, max_steps=100
        )

        assert steps > 0, "Should execute at least one step"
        assert terminal_event is not None, "Should have terminal event"

    def test_llm_episode_traffic_pattern_integration(self, llm_client):
        env = ATCEnv()
        client = llm_client

        observation, info = env.reset(task="traffic_pattern")

        success, steps, score, terminal_event, info = _run_llm_episode(
            env, client, max_steps=150
        )

        assert steps > 0, "Should execute at least one step"
        assert terminal_event is not None, "Should have terminal event"

    def test_llm_episode_reward_accumulation(self, llm_client):
        env = ATCEnv()
        client = llm_client

        observation, info = env.reset(task="single_approach")
        cumulative_reward = 0.0
        max_steps = 50

        for step in range(max_steps):
            prompt = generate_atc_prompt(observation)

            try:
                llm_response = client.generate_with_retry(prompt)
            except Exception:
                action = ATCAction(commands=[])
            else:
                try:
                    parsed = parse(llm_response)
                    commands = []

                    if isinstance(parsed, list):
                        for cmd in parsed:
                            cmd_str = _build_command_string(cmd)
                            if cmd_str:
                                commands.append(cmd_str)
                    else:
                        cmd_str = _build_command_string(parsed)
                        if cmd_str:
                            commands.append(cmd_str)

                    action = ATCAction(commands=commands)
                except ParseError:
                    action = ATCAction(commands=[])

            observation, reward, done, _, info = env.step(action)
            cumulative_reward += reward

            if done:
                break

        assert info.get("cumulative_reward") == cumulative_reward
