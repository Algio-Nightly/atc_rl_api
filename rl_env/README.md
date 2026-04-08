# ATC RL Environment

Reinforcement learning environment for Air Traffic Control simulation. Train LLM agents to manage aircraft approaches, handle traffic patterns, and operate in storm conditions.

## Overview

The environment simulates a radar-controlled airspace around a single airport (HEAT). Agents receive structured observations of aircraft positions, motions, and intents, then issue ATC commands to guide aircraft safely to landing.

Supports integration with Meta OpenEnv for RL training workflows.

## Quick Start

```bash
pip install -r rl_env/requirements.txt

export HF_TOKEN=your_huggingface_token
export MODEL_NAME=meta-llama/Llama-3.3-70B-Instruct
export API_BASE_URL=https://api.example.com/v1

python rl_env/inference.py
```

## Tasks

| Task | Aircraft | Difficulty | Description |
|------|----------|------------|-------------|
| `single_approach` | 1 | Easy | Single aircraft approach, learn basic navigation |
| `traffic_pattern` | 4 | Medium | Four aircraft from cardinal directions, basic separation |
| `storm_traffic` | 10 | Hard | Ten aircraft with wind effects, multi-aircraft management |

## Architecture

```
                    +------------------+
                    |   LLM Client     |
                    |  (inference.py)  |
                    +--------+---------+
                             |
                             v
                    +------------------+
                    |    ATCEnv        |
                    | (environment.py) |
                    +--------+---------+
                             |
          +------------------+------------------+
          |                  |                  |
          v                  v                  v
   +-------------+    +-------------+    +-------------+
   |  Simulation |    |   Command   |    |   Rubrics   |
   |   Engine    |    |   Parser    |    | (reward_fn) |
   +-------------+    +-------------+    +-------------+
          |
          v
   +-------------+
   |   Aircraft  |
   |   States    |
   +-------------+
```

**Core Components:**

- `ATCEnv` - Main RL environment interface (reset, step)
- `SimulationEngine` - Physics simulation and aircraft state
- `CommandParser` - Parses natural language commands into actions
- `ATCRubric` - Reward calculation based on task objectives

**Data Models:**

- `ATCAction` - Commands issued to aircraft (heading, altitude, speed, etc.)
- `ATCObservation` - Structured environment state for agent consumption
- `ATCAircraft` - Aircraft state (position, motion, intent, alerts)

## API Reference

```python
from rl_env import ATCEnv, ATCAction, ATCObservation

env = ATCEnv()

# Start new episode
observation, info = env.reset(task="single_approach")

# Execute action
observation, reward, done, truncated, info = env.step(ATCAction(commands=[
    "ATC DIRECT RL001 TO N",
    "ATC ALTITUDE RL001 3000"
]))

# Query state
state = env.state  # episode_id, step_count, task_name, cumulative_reward
```

**Available Commands:**

| Command | Parameters | Description |
|---------|------------|-------------|
| `ALTITUDE` | `altitude` | Set target altitude in feet |
| `SPEED` | `speed` | Set target speed in knots |
| `DIRECT` | `waypoint` | Clear direct to waypoint |
| `LAND` | `runway` | Clear to land on runway |
| `HOLD` | `waypoint`, `altitude` | Enter holding pattern |
| `RESUME` | - | Resume normal navigation |

## Testing

```bash
pytest rl_env/tests/ -v
```

Test categories:

- `test_environment.py` - Core environment functionality
- `test_parsers.py` - Command parsing
- `test_rubrics.py` - Reward calculation
- `test_tasks.py` - Task configurations

## Environment Details

**Observation Structure:**

```python
{
    "simulation_time": float,
    "aircraft": [{
        "callsign": str,
        "position": {"segment", "distance", "altitude", "target_altitude"},
        "motion": {"heading", "target_heading", "speed", "target_speed"},
        "intent": {"state", "assigned_runway", "distance_to_threshold", "next_waypoint"},
        "alerts": ["low_fuel", "critical_emergency"],
        "separation": {"closest_traffic", "distance", "conflict_risk"}
    }],
    "airport_status": {"active_runways", "runway_occupancy", "wind"}
}
```

**Terminal Conditions:**

- Aircraft collision (separation < 0.3km, altitude diff < 300ft)
- Separation violation
- Fuel exhaustion
- All aircraft landed or exited
- Max steps exceeded (200 per episode)
