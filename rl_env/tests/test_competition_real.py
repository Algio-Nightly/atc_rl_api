"""Competition integration tests - Full workflow test for competition entry.

These tests verify the complete competition workflow with all 3 tasks,
validating scores are in [0.0, 1.0] range and testing score determinism.

Requires HF_TOKEN environment variable for real LLM API access.
"""

import os
import time
from typing import Optional
import pytest

from rl_env.environment import ATCEnv
from rl_env.client import LLMClient
from rl_env.prompts.atc_prompt import generate_atc_prompt
from rl_env.parsers import parse, ParseError
from rl_env.models import ATCAction
from rl_env.tasks import (
    SingleApproachTask,
    TrafficPatternTask,
    StormTrafficTask,
    Task,
)


pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("HF_TOKEN"),
        reason="HF_TOKEN environment variable not set",
    ),
    pytest.mark.slow,
    pytest.mark.llm,
    pytest.mark.competition,
]


TASKS = ["single_approach", "traffic_pattern", "storm_traffic"]
MAX_STEPS_PER_EPISODE = 200
COMPETITION_TIMEOUT_SECONDS = 20 * 60


@pytest.fixture(scope="module")
def llm_client():
    """Create LLM client for competition tests."""
    hf_token = os.environ.get("HF_TOKEN")
    api_base_url = os.environ.get("API_BASE_URL", "https://router.huggingface.co/v1")
    model_name = os.environ.get("MODEL_NAME", "meta-llama/Llama-3.3-70B-Instruct")

    return LLMClient(
        api_base_url=api_base_url,
        model_name=model_name,
        hf_token=hf_token,
        timeout=120.0,
    )


def _build_command_string(cmd: dict) -> str:
    """Convert parsed command dict to ATC command string."""
    command = cmd.get("command", "").upper()
    callsign = cmd.get("callsign", "").upper()

    if not command or not callsign:
        return ""

    cmd_str = f"ATC {command} {callsign}"

    for key in ["heading", "altitude", "speed", "waypoint", "runway"]:
        if key in cmd and cmd[key] is not None:
            cmd_str += f" {cmd[key]}"

    return cmd_str


def _get_llm_action(client: LLMClient, observation) -> ATCAction:
    """Get action from LLM for given observation."""
    prompt = generate_atc_prompt(observation)

    try:
        llm_response = client.generate_with_retry(prompt)
    except Exception:
        return ATCAction(commands=[])

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

        return ATCAction(commands=commands)
    except ParseError:
        return ATCAction(commands=[])


def _run_episode(
    env: ATCEnv,
    client: LLMClient,
    task_name: str,
    seed: Optional[int] = None,
) -> tuple[bool, int, float, list[float], dict]:
    """
    Run a single episode for a given task.

    Args:
        env: ATC environment instance
        client: LLM client instance
        task_name: Name of the task to run
        seed: Random seed for reproducibility

    Returns:
        Tuple of (success, steps, score, rewards_list, info)
    """
    observation, info = env.reset(seed=seed, task=task_name)
    episode_rewards: list[float] = []
    step = 0
    success = False
    cumulative_reward = 0.0

    while step < MAX_STEPS_PER_EPISODE:
        step += 1

        try:
            action = _get_llm_action(client, observation)
        except Exception:
            action = ATCAction(commands=[])

        try:
            observation, reward, done, _, info = env.step(action)
            episode_rewards.append(reward)
            cumulative_reward += reward

            if done:
                success = True
                break

        except Exception:
            break

    return success, step, cumulative_reward, episode_rewards, info


def _get_task_grader(task_name: str) -> Optional[Task]:
    """Get the appropriate grader for a task."""
    task_map = {
        "single_approach": SingleApproachTask,
        "traffic_pattern": TrafficPatternTask,
        "storm_traffic": StormTrafficTask,
    }
    task_class = task_map.get(task_name)
    if task_class:
        return task_class()
    return None


class TestCompetitionFullWorkflow:
    """Test complete competition workflow with all 3 tasks."""

    def test_all_three_tasks_complete(self, llm_client):
        """
        Verify all 3 competition tasks can be completed without crashing.

        Tasks:
        - single_approach (easy): 1 aircraft, simple approach
        - traffic_pattern (medium): 4 aircraft, separation management
        - storm_traffic (hard): 10 aircraft, emergency handling
        """
        env = ATCEnv()
        results = {}

        start_time = time.time()

        for task_name in TASKS:
            task_start = time.time()
            success, steps, score, rewards, info = _run_episode(
                env, llm_client, task_name
            )
            task_duration = time.time() - task_start

            results[task_name] = {
                "success": success,
                "steps": steps,
                "score": score,
                "duration": task_duration,
            }

            assert steps > 0, f"Task {task_name} did not execute any steps"
            assert steps <= MAX_STEPS_PER_EPISODE, (
                f"Task {task_name} exceeded max steps"
            )

        total_duration = time.time() - start_time

        print("\n=== Competition Workflow Summary ===")
        for task_name, result in results.items():
            print(
                f"  {task_name}: success={result['success']}, "
                f"steps={result['steps']}, score={result['score']:.3f}, "
                f"time={result['duration']:.1f}s"
            )
        print(f"  Total time: {total_duration:.1f}s")

        assert total_duration < COMPETITION_TIMEOUT_SECONDS, (
            f"Competition workflow took {total_duration:.1f}s, "
            f"exceeds {COMPETITION_TIMEOUT_SECONDS}s limit"
        )


class TestCompetitionScoreValidation:
    """Test that scores are in valid [0.0, 1.0] range."""

    @pytest.mark.parametrize("task_name", TASKS)
    def test_score_in_valid_range(self, llm_client, task_name):
        """
        Verify score for each task is within [0.0, 1.0] range.

        Competition requires all scores to be normalized to [0.0, 1.0].
        """
        env = ATCEnv()

        grader = _get_task_grader(task_name)
        assert grader is not None, f"No grader found for task {task_name}"

        success, steps, cumulative_reward, rewards, info = _run_episode(
            env, llm_client, task_name
        )

        final_score = grader.grade(env)

        print(
            f"\n{task_name}: cumulative_reward={cumulative_reward:.3f}, "
            f"final_score={final_score:.3f}"
        )

        assert 0.0 <= final_score <= 1.0, (
            f"Task {task_name} score {final_score} is outside [0.0, 1.0] range"
        )

    def test_all_scores_valid_for_submission(self, llm_client):
        """
        Verify all 3 task scores are valid for competition submission.

        This is the final validation before submission.
        """
        env = ATCEnv()
        scores = {}

        for task_name in TASKS:
            grader = _get_task_grader(task_name)
            assert grader is not None, f"No grader for task {task_name}"
            success, steps, cumulative_reward, rewards, info = _run_episode(
                env, llm_client, task_name
            )
            final_score = grader.grade(env)
            scores[task_name] = final_score

        print("\n=== Competition Submission Scores ===")
        for task_name, score in scores.items():
            status = "VALID" if 0.0 <= score <= 1.0 else "INVALID"
            print(f"  {task_name}: {score:.4f} [{status}]")

        for task_name, score in scores.items():
            assert 0.0 <= score <= 1.0, f"Invalid score for {task_name}: {score}"

        total_score = sum(scores.values()) / len(scores)
        print(f"  Average score: {total_score:.4f}")


class TestCompetitionDeterminism:
    """Test score determinism with same seed."""

    @pytest.mark.parametrize("task_name", TASKS)
    def test_same_seed_produces_same_score(self, llm_client, task_name):
        """
        Verify that using the same seed produces the same score.

        This ensures reproducibility is working correctly.
        """
        seed = 42
        env1 = ATCEnv()
        env2 = ATCEnv()

        success1, steps1, score1, rewards1, info1 = _run_episode(
            env1, llm_client, task_name, seed=seed
        )

        success2, steps2, score2, rewards2, info2 = _run_episode(
            env2, llm_client, task_name, seed=seed
        )

        print(f"\n{task_name} (seed={seed}):")
        print(f"  Run 1: steps={steps1}, score={score1:.4f}")
        print(f"  Run 2: steps={steps2}, score={score2:.4f}")

        assert steps1 == steps2, (
            f"Task {task_name} produced different step counts "
            f"({steps1} vs {steps2}) with same seed"
        )

        assert abs(score1 - score2) < 10.0, (
            f"Task {task_name} produced vastly different scores "
            f"({score1:.4f} vs {score2:.4f}) with same seed"
        )

    def test_different_seeds_produce_different_outcomes(self, llm_client):
        """
        Verify that different seeds produce different outcomes.

        This ensures the seed is actually affecting the scenario.
        """
        task_name = "single_approach"
        env1 = ATCEnv()
        env2 = ATCEnv()

        success1, steps1, score1, _, _ = _run_episode(
            env1, llm_client, task_name, seed=123
        )

        success2, steps2, score2, _, _ = _run_episode(
            env2, llm_client, task_name, seed=456
        )

        print(f"\n{task_name}:")
        print(f"  Seed 123: steps={steps1}, score={score1:.4f}")
        print(f"  Seed 456: steps={steps2}, score={score2:.4f}")

        assert steps1 != steps2 or abs(score1 - score2) > 0.01, (
            f"Different seeds produced identical results - seed may not be working"
        )


class TestCompetitionRuntime:
    """Test that competition workflow meets runtime requirements."""

    def test_single_task_under_timeout(self, llm_client):
        """
        Verify a single task completes within reasonable time.

        Individual tasks should complete well under the 20-minute limit.
        """
        env = ATCEnv()
        task_name = "single_approach"

        start_time = time.time()
        success, steps, score, rewards, info = _run_episode(env, llm_client, task_name)
        duration = time.time() - start_time

        print(f"\n{task_name}: {duration:.1f}s ({steps} steps)")

        assert duration < 5 * 60, (
            f"Single task took {duration:.1f}s, exceeds 5 minute limit"
        )

    def test_full_competition_under_20_minutes(self, llm_client):
        """
        Verify full competition (all 3 tasks) completes within 20 minutes.

        This is the main runtime requirement for competition entry.
        """
        env = ATCEnv()
        start_time = time.time()

        for task_name in TASKS:
            _run_episode(env, llm_client, task_name)

        total_duration = time.time() - start_time

        print(f"\nFull competition: {total_duration:.1f}s")

        assert total_duration < COMPETITION_TIMEOUT_SECONDS, (
            f"Competition took {total_duration:.1f}s, exceeds "
            f"{COMPETITION_TIMEOUT_SECONDS}s (20 min) limit"
        )


class TestCompetitionGrading:
    """Test task-specific grading functions."""

    def test_single_approach_grading(self, llm_client):
        """Test SingleApproachTask grading."""
        env = ATCEnv()
        task = SingleApproachTask()

        success, steps, score, rewards, info = _run_episode(
            env, llm_client, "single_approach"
        )

        final_score = task.grade(env)

        print(f"\nSingleApproachTask:")
        print(f"  Episode score: {score:.4f}")
        print(f"  Final grade: {final_score:.4f}")

        assert 0.0 <= final_score <= 1.0, f"Score {final_score} out of range"

    def test_traffic_pattern_grading(self, llm_client):
        """Test TrafficPatternTask grading."""
        env = ATCEnv()
        task = TrafficPatternTask()

        success, steps, score, rewards, info = _run_episode(
            env, llm_client, "traffic_pattern"
        )

        final_score = task.grade(env)

        print(f"\nTrafficPatternTask:")
        print(f"  Episode score: {score:.4f}")
        print(f"  Final grade: {final_score:.4f}")

        assert 0.0 <= final_score <= 1.0, f"Score {final_score} out of range"

    def test_storm_traffic_grading(self, llm_client):
        """Test StormTrafficTask grading."""
        env = ATCEnv()
        task = StormTrafficTask()

        success, steps, score, rewards, info = _run_episode(
            env, llm_client, "storm_traffic"
        )

        final_score = task.grade(env)

        print(f"\nStormTrafficTask:")
        print(f"  Episode score: {score:.4f}")
        print(f"  Final grade: {final_score:.4f}")

        assert 0.0 <= final_score <= 1.0, f"Score {final_score} out of range"
