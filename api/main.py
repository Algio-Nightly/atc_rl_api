# FastAPI application and route definitions

from fastapi import FastAPI, HTTPException
from core.engine import SimulationEngine
from api.schemas import FullSimulationState, CommandRequest

app = FastAPI(title="ATC RL API")

# Global simulation instance
engine = SimulationEngine()

@app.get("/state", response_model=FullSimulationState)
async def get_state():
    """Get the current simulation state"""
    return engine.get_full_state()

@app.post("/step")
async def step_simulation():
    """Step the simulation by 1s"""
    engine.step()
    return {"message": "Simulation stepped", "time": engine.simulation_time}

@app.post("/command")
async def send_command(request: CommandRequest):
    """Update aircraft flight control parameters"""
    if request.callsign not in engine.aircrafts:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    
    aircraft = engine.aircrafts[request.callsign]
    if request.new_heading is not None:
        aircraft.heading = request.new_heading
    if request.new_altitude is not None:
        aircraft.altitude = request.new_altitude
    if request.new_speed is not None:
        aircraft.speed = request.new_speed
        
    return {"status": "Command sent", "callsign": request.callsign}

@app.on_event("startup")
async def startup_event():
    """Add some test aircraft on startup"""
    engine.add_aircraft("AIC123", "NORTH")
    engine.add_aircraft("EMA456", "SOUTH")
