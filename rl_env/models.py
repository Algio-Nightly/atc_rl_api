from pydantic import BaseModel, Field
from typing import Optional


class Wind(BaseModel):
    heading: int = Field(ge=0, lt=360, description="Wind heading in degrees (0-359)")
    speed: int = Field(ge=0, le=100, description="Wind speed in knots")

    @classmethod
    def example(cls) -> "Wind":
        return cls(heading=270, speed=15)


class Position(BaseModel):
    segment: str = Field(
        description="Direction segment: North, North-East, East, South-East, South, South-West, West, North-West"
    )
    distance: float = Field(ge=0, description="Distance from airport center in km")
    altitude: int = Field(ge=0, description="Current altitude in feet")
    target_altitude: int = Field(ge=0, description="Target altitude in feet")

    @classmethod
    def example(cls) -> "Position":
        return cls(
            segment="North-East", distance=12.5, altitude=5000, target_altitude=3000
        )


class Motion(BaseModel):
    heading: float = Field(
        ge=0, lt=360, description="Current heading in degrees (0-359)"
    )
    target_heading: float = Field(
        ge=0, lt=360, description="Target heading in degrees (0-359)"
    )
    speed: int = Field(gt=0, le=600, description="Current speed in knots")
    target_speed: int = Field(gt=0, le=600, description="Target speed in knots")

    @classmethod
    def example(cls) -> "Motion":
        return cls(heading=285.0, target_heading=270.0, speed=250, target_speed=210)


class Intent(BaseModel):
    state: str = Field(
        description="Aircraft state: ENROUTE, HOLDING, APPROACH, LANDING, GO_AROUND, TAXIING, CRASHED"
    )
    assigned_runway: Optional[str] = Field(
        default=None, description="Assigned runway ID"
    )
    distance_to_threshold: Optional[float] = Field(
        default=None, ge=0, description="Distance to runway threshold in km"
    )
    next_waypoint: str = Field(description="Next waypoint or STAR name")

    @classmethod
    def example(cls) -> "Intent":
        return cls(
            state="APPROACH",
            assigned_runway="27L",
            distance_to_threshold=8.5,
            next_waypoint="JUTES",
        )


class Separation(BaseModel):
    closest_traffic: Optional[str] = Field(
        default=None, description="Callsign of closest aircraft"
    )
    distance: Optional[float] = Field(
        default=None, ge=0, description="Distance to closest traffic in km"
    )
    conflict_risk: str = Field(description="Conflict risk level: none, medium, high")

    @classmethod
    def example(cls) -> "Separation":
        return cls(closest_traffic="UAL456", distance=5.2, conflict_risk="medium")


class AirportStatus(BaseModel):
    active_runways: list[str] = Field(
        default_factory=list, description="List of active runway IDs"
    )
    runway_occupancy: dict[str, Optional[str]] = Field(
        default_factory=dict,
        description="Map of runway ID to occupying aircraft callsign",
    )
    wind: Wind

    @classmethod
    def example(cls) -> "AirportStatus":
        return cls(
            active_runways=["27L", "27R"],
            runway_occupancy={"27L": "AAL123", "27R": None},
            wind=Wind.example(),
        )


class AircraftObservation(BaseModel):
    callsign: str = Field(description="Unique aircraft identifier (e.g., AAL123)")
    position: Position
    motion: Motion
    intent: Intent
    alerts: list[str] = Field(
        default_factory=list, description="Active alerts: low_fuel, critical_emergency"
    )
    separation: Separation

    @classmethod
    def example(cls) -> "AircraftObservation":
        return cls(
            callsign="AAL123",
            position=Position.example(),
            motion=Motion.example(),
            intent=Intent.example(),
            alerts=["low_fuel"],
            separation=Separation.example(),
        )


class Metrics(BaseModel):
    simulation_time: float = Field(
        ge=0, description="Elapsed simulation time in seconds"
    )
    planes_landed: int = Field(ge=0, description="Total aircraft successfully landed")
    planes_active: int = Field(ge=0, description="Number of currently active aircraft")

    @classmethod
    def example(cls) -> "Metrics":
        return cls(simulation_time=1850.5, planes_landed=3, planes_active=7)


class ATCObservation(BaseModel):
    airport_status: AirportStatus
    aircraft: list[AircraftObservation] = Field(default_factory=list)
    metrics: Metrics

    @classmethod
    def example(cls) -> "ATCObservation":
        return cls(
            airport_status=AirportStatus.example(),
            aircraft=[AircraftObservation.example()],
            metrics=Metrics.example(),
        )


class ATCAction(BaseModel):
    commands: list[str] = Field(
        default_factory=list,
        description="List of ATC commands (e.g., ['ATC VECTOR AAL123 270'])",
    )
    thought: Optional[str] = Field(
        default=None, description="Chain-of-thought reasoning for the commands"
    )

    @classmethod
    def example(cls) -> "ATCAction":
        return cls(
            commands=["ATC VECTOR AAL123 270", "ATC ALTITUDE AAL123 3000"],
            thought="The aircraft AAL123 is deviating from the approach path. Vectoring to heading 270 to re-align with the ILS.",
        )


class ATCState(BaseModel):
    episode_id: Optional[str] = Field(
        default=None, description="Unique episode identifier"
    )
    step_count: int = Field(ge=0, description="Current step number in the episode")
    task_name: str = Field(description="Name of the current task/scenario")
    cumulative_reward: float = Field(description="Accumulated reward for the episode")

    @classmethod
    def example(cls) -> "ATCState":
        return cls(
            episode_id="ep_001",
            step_count=42,
            task_name="KJFK Approach Control",
            cumulative_reward=156.7,
        )
