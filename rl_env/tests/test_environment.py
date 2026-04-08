"""Unit tests for ATC environment (ATCEnv class)."""

import pytest

from rl_env import ATCEnv, ATCAction, ATCObservation, ATCState


class TestATCEnvImport:
    def test_atcenv_importable(self):
        from rl_env import ATCEnv

        assert ATCEnv is not None

    def test_models_importable(self):
        from rl_env import ATCAction, ATCObservation, ATCState

        assert ATCAction is not None
        assert ATCObservation is not None
        assert ATCState is not None


class TestATCEnvInit:
    def test_init_default_airport(self):
        env = ATCEnv(airport_code="VOCB")
        assert env.airport_code == "VOCB"
        assert env.engine is None
        assert env.episode_id is None
        assert env.step_count == 0
        assert env.cumulative_reward == 0.0

    def test_init_custom_airport(self):
        env = ATCEnv(airport_code="AIRP")
        assert env.airport_code == "AIRP"


class TestATCEnvReset:
    def test_reset_single_approach(self):
        env = ATCEnv(airport_code="VOCB")
        obs, info = env.reset(task="single_approach")
        assert isinstance(obs, ATCObservation)
        assert "episode_id" in info
        assert info["task_name"] == "single_approach"
        assert env.episode_id is not None
        assert env.step_count == 0
        assert env.cumulative_reward == 0.0

    def test_reset_traffic_pattern(self):
        env = ATCEnv(airport_code="VOCB")
        obs, info = env.reset(task="traffic_pattern")
        assert isinstance(obs, ATCObservation)
        assert info["task_name"] == "traffic_pattern"

    def test_reset_with_seed(self):
        env = ATCEnv(airport_code="VOCB")
        obs1, _ = env.reset(seed=42, task="single_approach")
        env2 = ATCEnv(airport_code="VOCB")
        obs2, _ = env2.reset(seed=42, task="single_approach")
        assert env.episode_id != env2.episode_id

    def test_reset_spawns_aircraft(self):
        env = ATCEnv(airport_code="VOCB")
        obs, info = env.reset(task="single_approach")
        assert len(obs.aircraft) >= 1
        assert obs.metrics.planes_active >= 1


class TestATCEnvStep:
    def test_step_empty_action(self):
        env = ATCEnv(airport_code="VOCB")
        env.reset(task="single_approach")
        action = ATCAction(commands=[])
        obs, reward, done, truncated, info = env.step(action)
        assert isinstance(obs, ATCObservation)
        assert isinstance(reward, float)
        assert isinstance(done, bool)
        assert isinstance(truncated, bool)
        assert isinstance(info, dict)
        assert env.step_count == 1

    def test_step_with_vector_command(self):
        env = ATCEnv(airport_code="VOCB")
        env.reset(task="single_approach")
        callsign = list(env.engine.aircrafts.keys())[0]
        action = ATCAction(commands=[f"ATC VECTOR {callsign} 270"])
        obs, reward, done, truncated, info = env.step(action)
        assert isinstance(obs, ATCObservation)
        assert env.step_count == 1

    def test_step_with_altitude_command(self):
        env = ATCEnv(airport_code="VOCB")
        env.reset(task="single_approach")
        callsign = list(env.engine.aircrafts.keys())[0]
        action = ATCAction(commands=[f"ATC ALTITUDE {callsign} 5000"])
        obs, reward, done, truncated, info = env.step(action)
        assert isinstance(obs, ATCObservation)

    def test_step_with_speed_command(self):
        env = ATCEnv(airport_code="VOCB")
        env.reset(task="single_approach")
        callsign = list(env.engine.aircrafts.keys())[0]
        action = ATCAction(commands=[f"ATC SPEED {callsign} 220"])
        obs, reward, done, truncated, info = env.step(action)
        assert isinstance(obs, ATCObservation)

    def test_step_updates_cumulative_reward(self):
        env = ATCEnv(airport_code="VOCB")
        env.reset(task="single_approach")
        initial_reward = env.cumulative_reward
        action = ATCAction(commands=[])
        _, reward, _, _, _ = env.step(action)
        assert env.cumulative_reward == initial_reward + reward

    def test_step_increments_step_count(self):
        env = ATCEnv(airport_code="VOCB")
        env.reset(task="single_approach")
        assert env.step_count == 0
        action = ATCAction(commands=[])
        env.step(action)
        assert env.step_count == 1
        env.step(action)
        assert env.step_count == 2


class TestATCEnvState:
    def test_state_property(self):
        env = ATCEnv(airport_code="VOCB")
        env.reset(task="single_approach")
        state = env.state
        assert isinstance(state, ATCState)
        assert state.episode_id == env.episode_id
        assert state.step_count == env.step_count
        assert state.task_name == env.task_name
        assert state.cumulative_reward == env.cumulative_reward

    def test_state_after_steps(self):
        env = ATCEnv(airport_code="VOCB")
        env.reset(task="single_approach")
        action = ATCAction(commands=[])
        for _ in range(5):
            env.step(action)
        state = env.state
        assert state.step_count == 5
        assert state.cumulative_reward != 0.0


class TestATCEnvObservationStructure:
    def test_observation_has_required_fields(self):
        env = ATCEnv(airport_code="VOCB")
        env.reset(task="single_approach")
        obs = env._build_observation()
        assert hasattr(obs, "airport_status")
        assert hasattr(obs, "aircraft")
        assert hasattr(obs, "metrics")

    def test_observation_airport_status(self):
        env = ATCEnv(airport_code="VOCB")
        env.reset(task="single_approach")
        obs = env._build_observation()
        assert hasattr(obs.airport_status, "active_runways")
        assert hasattr(obs.airport_status, "runway_occupancy")
        assert hasattr(obs.airport_status, "wind")

    def test_observation_aircraft_fields(self):
        env = ATCEnv(airport_code="VOCB")
        env.reset(task="single_approach")
        obs = env._build_observation()
        if len(obs.aircraft) > 0:
            ac = obs.aircraft[0]
            assert hasattr(ac, "callsign")
            assert hasattr(ac, "position")
            assert hasattr(ac, "motion")
            assert hasattr(ac, "intent")
            assert hasattr(ac, "alerts")
            assert hasattr(ac, "separation")

    def test_observation_metrics(self):
        env = ATCEnv(airport_code="VOCB")
        env.reset(task="single_approach")
        obs = env._build_observation()
        assert hasattr(obs.metrics, "simulation_time")
        assert hasattr(obs.metrics, "planes_landed")
        assert hasattr(obs.metrics, "planes_active")


class TestATCActionModel:
    def test_action_with_commands(self):
        action = ATCAction(commands=["ATC VECTOR AAL123 270"])
        assert len(action.commands) == 1
        assert action.commands[0] == "ATC VECTOR AAL123 270"

    def test_action_with_thought(self):
        action = ATCAction(
            commands=["ATC VECTOR AAL123 270"],
            thought="Vectoring to align with approach",
        )
        assert action.thought == "Vectoring to align with approach"

    def test_action_example(self):
        action = ATCAction.example()
        assert len(action.commands) > 0
        assert "ATC VECTOR" in action.commands[0]


class TestATCStateModel:
    def test_state_example(self):
        state = ATCState.example()
        assert state.episode_id is not None
        assert state.step_count >= 0
        assert state.task_name is not None
        assert isinstance(state.cumulative_reward, float)


class TestATCEnvTerminalConditions:
    def test_done_false_initially(self):
        env = ATCEnv(airport_code="VOCB")
        env.reset(task="single_approach")
        action = ATCAction(commands=[])
        _, _, done, _, _ = env.step(action)
        assert done is False

    def test_info_contains_episode_metadata(self):
        env = ATCEnv(airport_code="VOCB")
        env.reset(task="single_approach")
        action = ATCAction(commands=[])
        _, _, _, _, info = env.step(action)
        assert "episode_id" in info
        assert "step_count" in info
        assert "task_name" in info
        assert "cumulative_reward" in info


class TestATCEnvStepReturnTypes:
    def test_step_returns_five_tuple(self):
        env = ATCEnv(airport_code="VOCB")
        env.reset(task="single_approach")
        result = env.step(ATCAction(commands=[]))
        assert isinstance(result, tuple)
        assert len(result) == 5
        obs, reward, done, truncated, info = result
        assert isinstance(obs, ATCObservation)
        assert isinstance(reward, float)
        assert isinstance(done, bool)
        assert isinstance(truncated, bool)
        assert isinstance(info, dict)

    def test_reset_returns_two_tuple(self):
        env = ATCEnv(airport_code="VOCB")
        result = env.reset(task="single_approach")
        assert isinstance(result, tuple)
        assert len(result) == 2
        obs, info = result
        assert isinstance(obs, ATCObservation)
        assert isinstance(info, dict)

    def test_step_info_contains_events(self):
        env = ATCEnv(airport_code="VOCB")
        env.reset(task="single_approach")
        _, _, _, _, info = env.step(ATCAction(commands=[]))
        assert "events" in info
        assert isinstance(info["events"], list)

    def test_step_info_contains_reward_breakdown(self):
        env = ATCEnv(airport_code="VOCB")
        env.reset(task="single_approach")
        _, _, _, _, info = env.step(ATCAction(commands=[]))
        assert "reward_breakdown" in info
        assert isinstance(info["reward_breakdown"], dict)
        assert "safety" in info["reward_breakdown"]
        assert "efficiency" in info["reward_breakdown"]

    def test_step_count_increments_by_one(self):
        env = ATCEnv(airport_code="VOCB")
        env.reset(task="single_approach")
        assert env.step_count == 0
        env.step(ATCAction(commands=[]))
        assert env.step_count == 1
        env.step(ATCAction(commands=[]))
        assert env.step_count == 2

    def test_rubric_resets_between_episodes(self):
        env = ATCEnv(airport_code="VOCB")
        env.reset(task="single_approach")
        env.step(ATCAction(commands=[]))
        env.reset(task="single_approach")
        assert env.step_count == 0
        assert env.cumulative_reward == 0.0

    def test_observation_has_telemetry_fields(self):
        env = ATCEnv(airport_code="VOCB")
        obs, _ = env.reset(task="single_approach")
        ac = obs.aircraft[0]
        assert hasattr(ac, "timing_stats")
        assert hasattr(ac, "safety_metrics")
        assert hasattr(ac, "command_rejections")
        assert hasattr(ac, "severity_index")

    def test_departure_task_config_exists(self):
        env = ATCEnv(airport_code="VOCB")
        obs, info = env.reset(task="single_departure")
        assert len(obs.aircraft) >= 1
        assert info["task_name"] == "single_departure"
