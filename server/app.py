"""OpenEnv-compatible HTTP server for the ATC RL Environment.

Exposes /reset, /step, and /state endpoints wrapping ATCEnv.
Designed to run inside a Docker container or HF Space on port 7860.
"""

from typing import Any, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rl_env.environment import ATCEnv
from rl_env.models import ATCAction, ATCObservation, ATCState

AVAILABLE_TASKS = [
    "single_approach",
    "traffic_pattern",
    "storm_traffic",
    "single_departure",
    "multi_departure",
    "mixed_operations",
]

app = FastAPI(
    title="ATC RL Environment",
    description="OpenEnv-compatible Air Traffic Control RL Environment",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

env = ATCEnv()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class ResetRequest(BaseModel):
    task: str = "single_approach"
    seed: Optional[int] = None


class ResetResponse(BaseModel):
    observation: ATCObservation
    done: bool = False
    info: dict[str, Any] = {}


class StepRequest(BaseModel):
    commands: list[str] = []
    thought: Optional[str] = None


class StepResponse(BaseModel):
    observation: ATCObservation
    reward: float
    done: bool
    truncated: bool
    info: dict[str, Any] = {}


class TaskInfo(BaseModel):
    name: str
    description: str
    difficulty: str
    aircraft_count: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/")
async def health():
    return {"status": "ok", "environment": "atc-rl-env", "version": "1.0.0"}


@app.post("/reset", response_model=ResetResponse)
async def reset(request: ResetRequest = ResetRequest()):
    """Reset the environment and start a new episode."""
    task = request.task if request.task in AVAILABLE_TASKS else "single_approach"
    observation, info = env.reset(seed=request.seed, task=task)
    return ResetResponse(observation=observation, done=False, info=info)


@app.post("/step", response_model=StepResponse)
async def step(request: StepRequest):
    """Execute one step with the given ATC commands."""
    action = ATCAction(commands=request.commands, thought=request.thought)
    observation, reward, done, truncated, info = env.step(action)

    serializable_info = _make_serializable(info)

    return StepResponse(
        observation=observation,
        reward=round(reward, 4),
        done=done,
        truncated=truncated,
        info=serializable_info,
    )


@app.get("/state", response_model=ATCState)
async def state():
    """Return current episode metadata."""
    return env.state


@app.get("/tasks", response_model=list[TaskInfo])
async def list_tasks():
    """List all available tasks with metadata."""
    task_metadata = {
        "single_approach": TaskInfo(
            name="single_approach",
            description="Guide a single aircraft to land safely",
            difficulty="easy",
            aircraft_count=1,
        ),
        "traffic_pattern": TaskInfo(
            name="traffic_pattern",
            description="Manage four aircraft arriving from cardinal directions",
            difficulty="medium",
            aircraft_count=4,
        ),
        "storm_traffic": TaskInfo(
            name="storm_traffic",
            description="Handle ten aircraft with wind effects and congestion",
            difficulty="hard",
            aircraft_count=10,
        ),
        "single_departure": TaskInfo(
            name="single_departure",
            description="Clear a single aircraft for taxi and takeoff",
            difficulty="easy",
            aircraft_count=1,
        ),
        "multi_departure": TaskInfo(
            name="multi_departure",
            description="Sequence three departures through a shared runway",
            difficulty="medium",
            aircraft_count=3,
        ),
        "mixed_operations": TaskInfo(
            name="mixed_operations",
            description="Coordinate simultaneous arrivals and departures",
            difficulty="hard",
            aircraft_count=6,
        ),
    }
    return [task_metadata[t] for t in AVAILABLE_TASKS]


def main() -> None:
    """Entry point for console script and direct execution."""
    import uvicorn

    uvicorn.run("server.app:app", host="0.0.0.0", port=7860)


def _make_serializable(info: dict[str, Any]) -> dict[str, Any]:
    """Ensure all values in the info dict are JSON-serializable."""
    clean: dict[str, Any] = {}
    for key, value in info.items():
        if key == "events":
            clean[key] = [
                {
                    k: str(v) if not isinstance(v, (int, float, bool, str, type(None))) else v
                    for k, v in evt.items()
                }
                for evt in (value or [])
            ]
        elif key == "reward_breakdown":
            clean[key] = {k: round(v, 4) for k, v in (value or {}).items()}
        else:
            clean[key] = value
    return clean


if __name__ == "__main__":
    main()
