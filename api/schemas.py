# Pydantic models for FastAPI

from pydantic import BaseModel, field_validator, Field
from typing import List, Optional, Literal, Union, Dict
from enum import Enum

class CommandType(str, Enum):
    ATC = "ATC"
    SIMULATION = "CMD"

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

class FullSimulationState(BaseModel):
    simulation_time: float
    is_terminal: bool
    active_runway: str
    wind_heading: float
    wind_speed: float
    time_scale: float
    aircrafts: Dict[str, AircraftState]
    events: List[dict]

class CommandRequest(BaseModel):
    type: CommandType
    command_id: str
    callsign: Optional[str] = None # Optional for global CMDs like TIME_SCALE
    new_heading: Optional[float] = None
    new_altitude: Optional[float] = None
    new_speed: Optional[float] = None
    time_scale: Optional[float] = None

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
    speed: int = 250
