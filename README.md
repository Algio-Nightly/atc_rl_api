---
title: ATC RL Environment
emoji: "✈️"
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
tags:
  - openenv
---

# ATC RL Environment

A reinforcement-learning environment where LLM agents act as **Air Traffic Controllers**.  
Agents receive structured radar observations — aircraft positions, speeds, headings, separation data, and airport status — and must issue ATC commands to guide aircraft safely through approach, departure, and mixed-traffic scenarios.

Built on a physics-based simulation engine with realistic runway geometry, STAR/SID procedures, wind modelling, and multi-aircraft separation logic.

## Motivation

Real-world ATC is among the most demanding cognitive tasks performed by humans: controllers must plan under uncertainty, maintain separation across dozens of aircraft, and adapt to weather in real time. This environment distils those challenges into a structured RL interface suitable for evaluating LLM reasoning, planning under constraints, and multi-step decision-making.

---

## Observation Space

Each step returns an `ATCObservation` (Pydantic model) containing:

| Field | Type | Description |
|-------|------|-------------|
| `airport_status` | `AirportStatus` | Active runways, runway occupancy, wind heading and speed |
| `aircraft` | `list[AircraftObservation]` | Per-aircraft state (see below) |
| `metrics` | `Metrics` | Simulation time, planes landed, planes active |

### AircraftObservation fields

| Field | Type | Description |
|-------|------|-------------|
| `callsign` | `str` | Unique aircraft ID (e.g. `RL001`) |
| `position` | `Position` | Segment, distance from center (km), altitude, target altitude |
| `motion` | `Motion` | Heading, target heading, speed, target speed |
| `intent` | `Intent` | State (`ENROUTE`, `APPROACH`, `LANDING`, …), assigned runway, distance to threshold |
| `alerts` | `list[str]` | Active alerts: `low_fuel`, `critical_emergency` |
| `separation` | `Separation` | Closest traffic callsign, distance (km), conflict risk (`none`/`medium`/`high`) |
| `timing_stats` | `TimingStats` | Total active time, time in current state, historical state durations |
| `safety_metrics` | `SafetyMetrics` | Separation warnings triggered, closest proximity |
| `command_rejections` | `list[str]` | Commands rejected this step (with reason) |
| `severity_index` | `float` | Emergency severity multiplier (≥ 1.0) |

## Action Space

Actions are submitted as `ATCAction`:

```python
ATCAction(
    commands=["ATC ALTITUDE RL001 3000", "ATC LAND RL001 RWY_1"],
    thought="Descending RL001 for final approach"  # optional chain-of-thought
)
```

### Available commands

| Command | Syntax | Description |
|---------|--------|-------------|
| `ALTITUDE` | `ATC ALTITUDE <callsign> <feet>` | Set target altitude |
| `SPEED` | `ATC SPEED <callsign> <knots>` | Set target speed |
| `HOLD` | `ATC HOLD <callsign>` | Enter holding pattern |
| `DIRECT` | `ATC DIRECT <callsign> TO <waypoint>` | Direct to waypoint/procedure |
| `LAND` | `ATC LAND <callsign> <runway_id>` | Clear to land on specified runway |
| `TAXI` | `ATC TAXI <callsign> <runway_id>` | Taxi to runway (departures) |
| `TAKEOFF` | `ATC TAKEOFF <callsign>` | Cleared for takeoff |
| `RESUME` | `ATC RESUME <callsign>` | Resume normal navigation |

---

## Tasks

| Task | Aircraft | Difficulty | Description |
|------|----------|------------|-------------|
| `single_approach` | 1 | Easy | Single aircraft approach — learn basic vectoring and landing clearance |
| `multi_departure` | 3 | Medium | Sequence three departures through a shared runway |
| `traffic_pattern` | 4 | Medium | Four arrivals from cardinal directions — practice separation and sequencing |

### Reward / Grading

All tasks use the composite `ATCRubric` which combines five weighted components:

| Component | Weight | Measures |
|-----------|--------|----------|
| Safety | 35% | Separation maintenance, collision avoidance |
| Efficiency | 30% | Time-to-landing, fuel awareness, direct routing |
| Compliance | 15% | Adherence to altitude/speed restrictions, procedure following |
| Format | 5% | Well-formed command syntax |
| Departure | 15% | Departure sequencing, runway utilisation |

Scores are normalised to the open interval **(0, 1)** using sigmoid normalisation in the inference script.

### Terminal conditions

- Aircraft collision (< 0.3 km lateral, < 300 ft vertical)
- Separation violation
- Fuel exhaustion / critical emergency
- All aircraft landed or exited airspace
- Max steps exceeded (200 per episode)

---

## Setup & Usage

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Docker (for containerised execution)

### Install dependencies

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

### Environment variables

```bash
export HF_TOKEN=<your-huggingface-token>
export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct      # or any OpenAI-compatible model
export API_BASE_URL=https://router.huggingface.co/v1
```

### Run inference

```bash
python inference.py
```

### Run the environment server locally

```bash
uvicorn server:app --host 0.0.0.0 --port 7860
```

### Docker

```bash
docker build -t atc-rl-env .
docker run -p 7860:7860 atc-rl-env
```

Then verify:

```bash
curl -X POST http://localhost:7860/reset -H "Content-Type: application/json" -d '{}'
```

### Python API (local, no server)

```python
from rl_env import ATCEnv, ATCAction

env = ATCEnv()
observation, info = env.reset(task="single_approach")

action = ATCAction(commands=["ATC ALTITUDE RL001 3000", "ATC LAND RL001 RWY_1"])
observation, reward, done, truncated, info = env.step(action)

state = env.state  # ATCState(episode_id, step_count, task_name, cumulative_reward)
```

---

## Baseline Scores

Baseline results using `Qwen/Qwen2.5-72B-Instruct` via HuggingFace Inference API:

| Task | Score | Steps | Success |
|------|-------|-------|---------|
| `single_approach` | ~0.35 | ~80 | Yes |
| `multi_departure` | ~0.25 | ~120 | Yes |
| `traffic_pattern` | ~0.20 | ~150 | Yes |

Average baseline score: **~0.27**

These scores represent a basic prompting strategy without fine-tuning or advanced reasoning chains. There is significant room for improvement through:
- Better prompt engineering and chain-of-thought reasoning
- Multi-step planning and lookahead
- Learning from environment feedback across episodes

---

## Testing

```bash
pytest rl_env/tests/ -v
```

## Validation

Run the pre-submission validator:

```bash
pip install openenv-core
openenv validate
```

---

## Project Structure

```
├── inference.py          # Competition inference script (root)
├── server.py             # OpenEnv HTTP server
├── openenv.yaml          # OpenEnv spec definition
├── Dockerfile            # UV-based container build
├── pyproject.toml        # Dependencies and project metadata
├── rl_env/
│   ├── environment.py    # ATCEnv — main RL environment
│   ├── models.py         # Pydantic observation/action/state models
│   ├── client.py         # LLM client wrapper
│   ├── parsers/          # ATC command parsing
│   ├── prompts/          # Prompt generation for LLM agents
│   ├── rubrics/          # Reward computation (safety, efficiency, compliance, …)
│   └── tasks/            # Task configurations and graders
├── core/
│   ├── engine.py         # Physics simulation engine
│   ├── aircraft.py       # Aircraft state machine
│   └── constants.py      # Shared constants
├── api/                  # Full simulation API (dev/visualiser)
└── airports/             # Airport configuration JSON files
```
