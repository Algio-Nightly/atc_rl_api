# Pydantic models for FastAPI

from pydantic import BaseModel, field_validator, Field
from typing import List, Optional, Literal, Union, Dict
from enum import Enum
import uuid

class CommandType(str, Enum):
    ATC = "ATC"
    SIMULATION = "CMD"

class ATCCommandID(str, Enum):
    ATC_VECTOR = "ATC_VECTOR"
    ATC_ALTITUDE = "ATC_ALTITUDE"
    ATC_SPEED = "ATC_SPEED"
    ATC_DIRECT_TO = "ATC_DIRECT_TO"
    ATC_HOLD = "ATC_HOLD"
    ATC_APPROACH = "ATC_APPROACH"
    ATC_LAND = "ATC_LAND"

class PilotMessageType(str, Enum):
    REQUEST = "REQUEST"
    REPORT = "REPORT"
    ACKNOWLEDGE = "ACKNOWLEDGE"

class AircraftState(BaseModel):
    # Identifiers
    callsign: str
    type: str
    weight_class: Literal["Light", "Medium", "Heavy"] 
    
    # Kinematics
    x: float
    y: float
    altitude: int = Field(ge=0, description="Altitude in feet")
    
    # Enforcing strict aviation math (0 to 359 degrees)
    heading: float = Field(ge=0, lt=360)
    target_heading: float = Field(ge=0, lt=360)
    
    speed: int = Field(gt=0, le=600, description="Speed in knots")
    target_speed: int = Field(gt=0, le=600)
    
    # System Status
    state: Literal["ENROUTE", "HOLDING", "APPROACH", "LANDING", "GO_AROUND", "TAXIING", "CRASHED"]
    fuel_level: float = Field(ge=0.0, le=100.0)
    emergency_index: int = Field(default=0, ge=0, le=3, description="0=Normal, 1=Low Fuel, 3=Critical")
    
    # Routing
    active_star: Optional[str] = None
    wp_index: int = 0
    is_holding: bool = False


class CommandRequest(BaseModel):
    type: CommandType
    command_id: Union[ATCCommandID, str]
    callsign: Optional[str] = None # Optional for global CMDs like TIME_SCALE
    waypoint_name: Optional[str] = None
    new_heading: Optional[float] = None
    new_altitude: Optional[float] = None
    new_speed: Optional[float] = None
    time_scale: Optional[float] = None
    wind_heading: Optional[float] = None
    wind_speed: Optional[float] = None

    @field_validator("command_id")
    @classmethod
    def validate_command_id_prefix(cls, v: str, info):
        c_type = info.data.get("type")
        if c_type == CommandType.ATC and not v.startswith("ATC"):
            raise ValueError("ATC command IDs must start with 'ATC'")
        if c_type == CommandType.SIMULATION and not v.startswith("CMD"):
            raise ValueError("Simulation command IDs must start with 'CMD'")
        return v

class PilotMessage(BaseModel):
    callsign: str
    msg_type: PilotMessageType
    content: str

class StarAssignmentRequest(BaseModel):
    callsign: str
    star_name: str

class WeatherUpdateRequest(BaseModel):
    wind_heading: float = Field(ge=0, lt=360)
    wind_speed: float = Field(ge=0, le=100)

class SpawnRequest(BaseModel):
    callsign: str
    type: str
    weight_class: Literal["Light", "Medium", "Heavy"]
    gate: str
    altitude: int = 10000
    heading: float = 0
    heading: float = 0
    speed: int = 250

# --- Configuration Schemas ---

class Point(BaseModel):
    x: float
    y: float

class LatLon(BaseModel):
    lat: float
    lon: float

class RunwayConfig(BaseModel):
    id: str
    heading: float
    length_km: float
    start: Point
    end: Point
    iaf: Point

class WaypointConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "WP"
    x: float
    y: float
    target_alt: int = 3000
    target_speed: int = 210
    is_iaf: bool = False
    holding_stack: List[str] = [] # List of aircraft callsigns currently holding here

class AirportConfig(BaseModel):
    airport_code: str
    name: str
    anchor: LatLon
    bounds: Dict[str, float] = {"width_km": 50, "height_km": 50}
    center: Point = Point(x=25, y=25)
    gates: Dict[str, Point]
    runways: List[RunwayConfig] = []
    # Global pool of waypoints: ID -> Config
    waypoints: Dict[str, WaypointConfig] = {}
    # gate -> runway -> waypoint_ids
    stars: Dict[str, Dict[str, List[str]]] = {}
    time_scale: float = 1.0

# --- Request Models ---

class AirportCreateRequest(BaseModel):
    airport_code: str
    name: str
    anchor_lat: float
    anchor_lon: float

class WaypointCreateRequest(BaseModel):
    airport_code: str
    x: float
    y: float
    name: Optional[str] = None
    target_alt: Optional[int] = 3000
    target_speed: Optional[int] = 210
    is_iaf: bool = False

class StarRouteSaveRequest(BaseModel):
    airport_code: str
    gate_id: str
    runway_id: str
    route_sequence: List[str] # List of waypoint IDs

class WaypointUpdateRequest(BaseModel):
    airport_code: str
    gate_id: str
    target_runway: str
    sequence_index: int
    name: Optional[str] = None
    target_alt: Optional[int] = None
    target_speed: Optional[int] = None

class WaypointDeleteRequest(BaseModel):
    airport_code: str
    gate_id: str
    target_runway: str
    sequence_index: int

class RunwayUpdateRequest(BaseModel):
    airport_code: str
    runway_id: str # Original ID for lookup
    new_id: Optional[str] = None
    heading: Optional[float] = None

class RunwayCreateRequest(BaseModel):
    airport_code: str
    runway_id: str
    length_km: float
    heading: float

class SimSetAirportRequest(BaseModel):
    airport_code: str

# --- Simulation State (End of file to avoid forward refs) ---

class RunwaySummary(BaseModel):
    id: str
    heading: float
    start: List[float]
    end: List[float]

class AirportSummary(BaseModel):
    name: str
    lat: float
    lon: float
    airport_code: str
    runways: List[RunwaySummary]

class FullSimulationState(BaseModel):
    simulation_time: float
    is_terminal: bool
    active_runways: List[str]
    wind_heading: float
    wind_speed: float
    time_scale: float
    aircrafts: Dict[str, AircraftState]
    events: List[dict]
    config: Optional[AirportConfig] = None
    airports: List[AirportSummary] = []
