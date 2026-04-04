# Pydantic models for FastAPI

from pydantic import BaseModel
from typing import List, Optional

class AircraftState(BaseModel):
    callsign: str
    x: float
    y: float
    altitude: float
    heading: float
    speed: float

class FullSimulationState(BaseModel):
    time: float
    aircrafts: List[AircraftState]

class CommandRequest(BaseModel):
    callsign: str
    new_heading: Optional[float] = None
    new_altitude: Optional[float] = None
    new_speed: Optional[float] = None
