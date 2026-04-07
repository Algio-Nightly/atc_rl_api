"""Unit tests for Task classes."""

import pytest

from rl_env import ATCEnv, ATCAction
from rl_env.tasks import (
    Task,
    SingleApproachTask,
    TrafficPatternTask,
    StormTrafficTask,
)


class TestTaskImport:
    def test_task_importable(self):
        from rl_env.tasks import Task

        assert Task is not None

    def test_single_approach_importable(self):
        from rl_env.tasks import SingleApproachTask

        assert SingleApproachTask is not None

    def test_traffic_pattern_importable(self):
        from rl_env.tasks import TrafficPatternTask

        assert TrafficPatternTask is not None

    def test_storm_traffic_importable(self):
        from rl_env.tasks import StormTrafficTask

        assert StormTrafficTask is not None


class TestTaskBaseClass:
    def test_task_is_abstract(self):
        from abc import ABC

        assert issubclass(Task, ABC)

    def test_task_name_property(self):
        task = SingleApproachTask()
        assert task.name == "SingleApproachTask"

    def test_task_difficulty_property(self):
        task = SingleApproachTask()
        assert hasattr(task, "difficulty")


class TestSingleApproachTask:
    def test_task_setup(self):
        env = ATCEnv()
        task = SingleApproachTask()
        task.setup(env)
        assert env.engine is not None
        assert len(env.engine.aircrafts) >= 1

    def test_task_difficulty(self):
        task = SingleApproachTask()
        assert task.difficulty == "easy"

    def test_task_grade_returns_float(self):
        env = ATCEnv()
        task = SingleApproachTask()
        task.setup(env)
        score = task.grade(env)
        assert isinstance(score, float)

    def test_task_grade_in_range(self):
        env = ATCEnv()
        task = SingleApproachTask()
        task.setup(env)
        score = task.grade(env)
        assert 0.0 <= score <= 1.0

    def test_task_is_complete_returns_bool(self):
        env = ATCEnv()
        task = SingleApproachTask()
        task.setup(env)
        done = task.is_complete(env)
        assert isinstance(done, bool)


class TestTrafficPatternTask:
    def test_task_setup(self):
        env = ATCEnv()
        task = TrafficPatternTask()
        task.setup(env)
        assert env.engine is not None
        assert len(env.engine.aircrafts) >= 4

    def test_task_difficulty(self):
        task = TrafficPatternTask()
        assert task.difficulty == "medium"

    def test_task_grade_returns_float(self):
        env = ATCEnv()
        task = TrafficPatternTask()
        task.setup(env)
        score = task.grade(env)
        assert isinstance(score, float)

    def test_task_grade_in_range(self):
        env = ATCEnv()
        task = TrafficPatternTask()
        task.setup(env)
        score = task.grade(env)
        assert 0.0 <= score <= 1.0

    def test_task_is_complete_returns_bool(self):
        env = ATCEnv()
        task = TrafficPatternTask()
        task.setup(env)
        done = task.is_complete(env)
        assert isinstance(done, bool)


class TestStormTrafficTask:
    def test_task_setup(self):
        env = ATCEnv()
        task = StormTrafficTask()
        task.setup(env)
        assert env.engine is not None
        assert len(env.engine.aircrafts) >= 10

    def test_task_difficulty(self):
        task = StormTrafficTask()
        assert task.difficulty == "hard"

    def test_task_grade_returns_float(self):
        env = ATCEnv()
        task = StormTrafficTask()
        task.setup(env)
        score = task.grade(env)
        assert isinstance(score, float)

    def test_task_grade_in_range(self):
        env = ATCEnv()
        task = StormTrafficTask()
        task.setup(env)
        score = task.grade(env)
        assert 0.0 <= score <= 1.0

    def test_task_is_complete_returns_bool(self):
        env = ATCEnv()
        task = StormTrafficTask()
        task.setup(env)
        done = task.is_complete(env)
        assert isinstance(done, bool)

    def test_wind_update_method(self):
        env = ATCEnv()
        task = StormTrafficTask()
        task.setup(env)
        task.update_wind(env)


class TestTaskIntegration:
    def test_single_approach_episode_flow(self):
        env = ATCEnv()
        task = SingleApproachTask()
        task.setup(env)

        action = ATCAction(commands=[])
        for _ in range(10):
            if task.is_complete(env):
                break
            env.step(action)

        score = task.grade(env)
        assert 0.0 <= score <= 1.0

    def test_traffic_pattern_episode_flow(self):
        env = ATCEnv()
        task = TrafficPatternTask()
        task.setup(env)

        action = ATCAction(commands=[])
        for _ in range(10):
            if task.is_complete(env):
                break
            env.step(action)

        score = task.grade(env)
        assert 0.0 <= score <= 1.0

    def test_storm_traffic_episode_flow(self):
        env = ATCEnv()
        task = StormTrafficTask()
        task.setup(env)

        action = ATCAction(commands=[])
        for _ in range(10):
            if task.is_complete(env):
                break
            env.step(action)
            task.update_wind(env)

        score = task.grade(env)
        assert 0.0 <= score <= 1.0
