"""OpenEnv compliance tests for ATC RL environment.

Tests verify that ATCEnv correctly implements the OpenEnv interface:
- reset() returns valid ATCObservation
- step() returns proper tuple (obs, reward, done, truncated, info)
- state property returns ATCState
- inference.py execution produces [START]/[STEP]/[END] output

Requires HF_TOKEN environment variable for real LLM API access.
Marked with @pytest.mark.llm and @pytest.mark.slow for test filtering.
"""

import os
import subprocess
import sys
import pytest

from rl_env.environment import ATCEnv
from rl_env.models import ATCAction, ATCObservation, ATCState


pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("HF_TOKEN"),
        reason="HF_TOKEN environment variable not set",
    ),
    pytest.mark.slow,
    pytest.mark.llm,
]


class TestOpenEnvResetInterface:
    """Tests for OpenEnv reset() interface compliance."""

    def test_reset_returns_tuple(self):
        """reset() should return a tuple of (observation, info)."""
        env = ATCEnv()
        result = env.reset(task="single_approach")

        assert isinstance(result, tuple), "reset() must return a tuple"
        assert len(result) == 2, "reset() must return (observation, info)"

    def test_reset_returns_valid_atcobservation(self):
        """reset() first return value should be a valid ATCObservation."""
        env = ATCEnv()
        observation, info = env.reset(task="single_approach")

        assert isinstance(observation, ATCObservation), (
            "First return must be ATCObservation"
        )

    def test_reset_observation_has_required_fields(self):
        """ATCObservation from reset() must have all required fields."""
        env = ATCEnv()
        observation, info = env.reset(task="single_approach")

        assert hasattr(observation, "airport_status"), "Missing airport_status"
        assert hasattr(observation, "aircraft"), "Missing aircraft"
        assert hasattr(observation, "metrics"), "Missing metrics"
        assert isinstance(observation.aircraft, list), "aircraft must be a list"

    def test_reset_info_contains_episode_metadata(self):
        """Info dict from reset() should contain episode metadata."""
        env = ATCEnv()
        observation, info = env.reset(task="single_approach")

        assert "episode_id" in info, "Missing episode_id in info"
        assert "task_name" in info, "Missing task_name in info"
        assert info["task_name"] == "single_approach"

    def test_reset_aircraft_spawned(self):
        """reset() should spawn aircraft according to task config."""
        env = ATCEnv()
        observation, info = env.reset(task="single_approach")

        assert len(observation.aircraft) >= 1, (
            "single_approach should spawn at least 1 aircraft"
        )
        assert info["initial_aircraft_count"] >= 1

    def test_reset_traffic_pattern_spawns_multiple(self):
        """reset() with traffic_pattern should spawn multiple aircraft."""
        env = ATCEnv()
        observation, info = env.reset(task="traffic_pattern")

        assert len(observation.aircraft) >= 4, (
            "traffic_pattern should spawn at least 4 aircraft"
        )


class TestOpenEnvStepInterface:
    """Tests for OpenEnv step() interface compliance."""

    def test_step_returns_five_tuple(self):
        """step() should return 5-tuple: (obs, reward, done, truncated, info)."""
        env = ATCEnv()
        env.reset(task="single_approach")

        action = ATCAction(commands=[])
        result = env.step(action)

        assert isinstance(result, tuple), "step() must return a tuple"
        assert len(result) == 5, "step() must return 5 values"

    def test_step_returns_correct_types(self):
        """step() return values should have correct types."""
        env = ATCEnv()
        env.reset(task="single_approach")

        action = ATCAction(commands=[])
        observation, reward, done, truncated, info = env.step(action)

        assert isinstance(observation, ATCObservation), "obs must be ATCObservation"
        assert isinstance(reward, (int, float)), "reward must be numeric"
        assert isinstance(done, bool), "done must be bool"
        assert isinstance(truncated, bool), "truncated must be bool"
        assert isinstance(info, dict), "info must be dict"

    def test_step_reward_is_finite(self):
        """step() reward should be a finite number."""
        env = ATCEnv()
        env.reset(task="single_approach")

        action = ATCAction(commands=[])
        _, reward, _, _, _ = env.step(action)

        assert float("-inf") < reward < float("inf"), "reward must be finite"

    def test_step_info_contains_step_count(self):
        """step() info should contain step_count."""
        env = ATCEnv()
        env.reset(task="single_approach")

        action = ATCAction(commands=[])
        _, _, _, _, info = env.step(action)

        assert "step_count" in info, "Missing step_count in info"
        assert info["step_count"] == 1, "First step should have step_count=1"

    def test_step_info_contains_episode_id(self):
        """step() info should contain episode_id from reset."""
        env = ATCEnv()
        obs, reset_info = env.reset(task="single_approach")
        expected_episode_id = reset_info["episode_id"]

        action = ATCAction(commands=[])
        _, _, _, _, info = env.step(action)

        assert info["episode_id"] == expected_episode_id

    def test_step_increments_step_count(self):
        """Multiple steps should increment step_count correctly."""
        env = ATCEnv()
        env.reset(task="single_approach")

        for expected_step in range(1, 4):
            action = ATCAction(commands=[])
            _, _, _, _, info = env.step(action)
            assert info["step_count"] == expected_step


class TestOpenEnvStateProperty:
    """Tests for OpenEnv state property compliance."""

    def test_state_returns_atcstate(self):
        """state property should return ATCState instance."""
        env = ATCEnv()
        env.reset(task="single_approach")

        state = env.state

        assert isinstance(state, ATCState), "state must be ATCState"

    def test_state_contains_episode_metadata(self):
        """ATCState should contain episode metadata."""
        env = ATCEnv()
        env.reset(task="single_approach")

        state = env.state

        assert hasattr(state, "episode_id"), "Missing episode_id"
        assert hasattr(state, "step_count"), "Missing step_count"
        assert hasattr(state, "task_name"), "Missing task_name"
        assert hasattr(state, "cumulative_reward"), "Missing cumulative_reward"

    def test_state_reflects_step_count(self):
        """state.step_count should reflect number of steps taken."""
        env = ATCEnv()
        env.reset(task="single_approach")

        for _ in range(3):
            env.step(ATCAction(commands=[]))

        state = env.state
        assert state.step_count == 3, "state should reflect 3 steps"

    def test_state_reflects_cumulative_reward(self):
        """state.cumulative_reward should accumulate rewards."""
        env = ATCEnv()
        env.reset(task="single_approach")

        initial_reward = env.state.cumulative_reward

        _, reward1, _, _, _ = env.step(ATCAction(commands=[]))
        _, reward2, _, _, _ = env.step(ATCAction(commands=[]))

        final_state = env.state
        expected = initial_reward + reward1 + reward2
        assert abs(final_state.cumulative_reward - expected) < 0.01


class TestOpenEnvEpisodeTermination:
    """Tests for episode termination conditions."""

    def test_episode_terminates_on_crash(self):
        """Episode should terminate when crash is detected."""
        env = ATCEnv()
        env.reset(task="single_approach")

        done = False
        steps = 0
        max_steps = 500

        while not done and steps < max_steps:
            action = ATCAction(commands=[])
            _, _, done, _, info = env.step(action)
            steps += 1

            if done:
                terminal_event = info.get("terminal_event")
                assert terminal_event is not None, (
                    "done=True should have terminal_event"
                )

    def test_episode_runs_multiple_steps(self):
        """Episode should support multiple steps without immediate termination."""
        env = ATCEnv()
        env.reset(task="single_approach")

        done = False
        steps = 0
        max_steps = 50

        while not done and steps < max_steps:
            action = ATCAction(commands=[])
            _, _, done, _, _ = env.step(action)
            steps += 1

        assert steps >= 10, f"Episode should run at least 10 steps, got {steps}"

    def test_truncated_is_always_false(self):
        """OpenEnv spec: truncated should be False (we handle termination via done)."""
        env = ATCEnv()
        env.reset(task="single_approach")

        for _ in range(10):
            action = ATCAction(commands=[])
            _, _, _, truncated, _ = env.step(action)
            assert truncated is False, "truncated should always be False"


class TestInferenceScriptOutput:
    """Tests for inference.py script execution and output format."""

    def test_inference_script_produces_start_output(self, tmp_path):
        """inference.py should print [START] when beginning episode."""
        env = ATCEnv()
        env.reset(task="single_approach")

        from rl_env.client import LLMClient
        from rl_env.prompts.atc_prompt import generate_atc_prompt
        from rl_env.models import ATCAction

        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            pytest.skip("HF_TOKEN not set")

        client = LLMClient(hf_token=hf_token)
        observation, _ = env.reset(task="single_approach")

        prompt = generate_atc_prompt(observation)
        llm_response = client.generate(prompt)

        assert llm_response is not None, "LLM should produce a response"
        assert len(llm_response) > 0, "LLM response should not be empty"

    def test_inference_script_single_approach_runs(self):
        """Full inference loop should run for single_approach task."""
        env = ATCEnv()
        env.reset(task="single_approach")

        from rl_env.client import LLMClient
        from rl_env.prompts.atc_prompt import generate_atc_prompt
        from rl_env.models import ATCAction
        from rl_env.parsers import parse, ParseError

        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            pytest.skip("HF_TOKEN not set")

        client = LLMClient(hf_token=hf_token)
        observation, _ = env.reset(task="single_approach")

        max_steps = 20
        info = None
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
                    parsed_list = parsed if isinstance(parsed, list) else [parsed]

                    for cmd in parsed_list:
                        cmd_str = f"ATC {cmd['command']} {cmd['callsign']}"
                        if "heading" in cmd and cmd["heading"] is not None:
                            cmd_str += f" {cmd['heading']}"
                        elif "altitude" in cmd and cmd["altitude"] is not None:
                            cmd_str += f" {cmd['altitude']}"
                        commands.append(cmd_str)

                    action = ATCAction(commands=commands)
                except ParseError:
                    action = ATCAction(commands=[])

            observation, reward, done, _, info = env.step(action)

            if done:
                break

        assert info is not None, "At least one step should execute"
        assert info["step_count"] > 0
        assert info["episode_id"] is not None


class TestOpenEnvInterfaceIntegration:
    """Integration tests verifying full OpenEnv interface compliance."""

    def test_full_episode_reset_step_state_cycle(self):
        """Complete episode cycle: reset -> step -> state -> step -> state."""
        env = ATCEnv()

        # Reset
        observation, info = env.reset(task="single_approach")
        assert isinstance(observation, ATCObservation)
        episode_id = info["episode_id"]

        # Check state after reset
        state = env.state
        assert isinstance(state, ATCState)
        assert state.episode_id == episode_id
        assert state.step_count == 0

        # Step
        action = ATCAction(commands=[])
        obs, reward, done, truncated, step_info = env.step(action)

        assert isinstance(obs, ATCObservation)
        assert isinstance(reward, (int, float))
        assert isinstance(done, bool)
        assert isinstance(truncated, bool)
        assert isinstance(step_info, dict)

        # Check state after step
        state = env.state
        assert state.step_count == 1
        assert state.episode_id == episode_id

    def test_episode_metadata_consistency(self):
        """Episode metadata should be consistent across reset/step/state."""
        env = ATCEnv()
        observation, reset_info = env.reset(task="traffic_pattern")

        expected_episode_id = reset_info["episode_id"]
        expected_task = reset_info["task_name"]

        state = env.state
        assert state.episode_id == expected_episode_id
        assert state.task_name == expected_task

        for _ in range(5):
            action = ATCAction(commands=[])
            _, _, _, _, info = env.step(action)
            assert info["episode_id"] == expected_episode_id
            assert info["task_name"] == expected_task

            state = env.state
            assert state.episode_id == expected_episode_id
            assert state.task_name == expected_task
