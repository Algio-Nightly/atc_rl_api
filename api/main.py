import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from atc_rl_api.core.engine import SimulationEngine
from atc_rl_api.api.schemas import (
    FullSimulationState, 
    CommandRequest, 
    PilotMessage, 
    StarAssignmentRequest, 
    WeatherUpdateRequest,
    SpawnRequest,
    CommandType
)

# Global simulation instance
engine = SimulationEngine()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the simulation background task
    task = asyncio.create_task(engine.run())
    yield
    # Stop the simulation
    engine.is_active = False
    await task

app = FastAPI(title="ATC RL API", lifespan=lifespan)

@app.get("/state", response_model=FullSimulationState)
async def get_state():
    """Get the current simulation state and clear the event buffer"""
    return engine.get_full_state()

@app.post("/reset")
async def reset_simulation():
    """Wipe the simulation back to zero state"""
    engine.reset_environment()
    return {"status": "Simulation reset"}

@app.post("/spawn")
async def spawn_aircraft(request: SpawnRequest):
    """Spawn a new aircraft via command"""
    success = engine.add_aircraft(
        callsign=request.callsign,
        ac_type=request.type,
        weight_class=request.weight_class,
        gate=request.gate,
        altitude=request.altitude,
        heading=request.heading,
        speed=request.speed
    )
    if not success:
        raise HTTPException(status_code=400, detail="Failed to spawn aircraft (invalid gate?)")
    return {"status": "Aircraft spawned", "callsign": request.callsign}

@app.post("/command")
async def send_command(request: CommandRequest):
    """General command endpoint for ATC and Administrative actions"""
    
    # 1. Handle Administrative/System Commands (CMD)
    if request.type == CommandType.SIMULATION:
        if request.command_id == "CMD_SET_TIME_SCALE" and request.time_scale is not None:
            engine.time_scale = request.time_scale
            return {"status": "Time scale updated", "new_scale": engine.time_scale}
        
        # We could also handle CMD_SPAWN here if needed, but we have a dedicated endpoint now
        return {"status": "Command received but no matching system logic found"}

    # 2. Handle ATC Commands
    if request.callsign not in engine.aircrafts:
        raise HTTPException(status_code=404, detail=f"Aircraft '{request.callsign}' not found")
        
    aircraft = engine.aircrafts[request.callsign]
    
    # Custom ATC command logic
    if request.command_id == "ATC_HOLD":
        from atc_rl_api.core.constants import HOLDING_FIXES
        # Find nearest holding fix or use gate-based
        # We'll use a simple heuristic: if they spawned at gate X, use fix X.
        # Check active_star first
        gate_origin = aircraft.active_star or "NORTH"
        aircraft.holding_fix = HOLDING_FIXES.get(gate_origin, HOLDING_FIXES["NORTH"])
        aircraft.state = "HOLDING"
        return {"status": "Holding pattern entered", "callsign": aircraft.callsign}
        
    if request.command_id == "ATC_RESUME":
        aircraft.state = "ENROUTE"
        # Logic to re-intercept STAR? For now, it will just track the nearest waypoint
        return {"status": "Resuming STAR navigation", "callsign": aircraft.callsign}

    # Standard Flight Control
    if request.new_heading is not None:
        aircraft.target_heading = request.new_heading
    if request.new_altitude is not None:
        aircraft.target_alt = request.new_altitude
    if request.new_speed is not None:
        aircraft.target_speed = request.new_speed
        
    return {
        "status": "ATC Command processed", 
        "command_id": request.command_id,
        "callsign": request.callsign
    }

@app.post("/update-weather")
async def update_weather(request: WeatherUpdateRequest):
    """Update wind conditions and active runway"""
    engine.update_weather(request.wind_heading, request.wind_speed)
    return {
        "status": "Weather updated",
        "active_runway": engine.active_runway,
        "wind_heading": engine.wind_heading,
        "wind_speed": engine.wind_speed
    }
