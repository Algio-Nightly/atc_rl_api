import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from atc_rl_api.core.engine import SimulationEngine
from atc_rl_api.api.schemas import (
    FullSimulationState, 
    CommandRequest, 
    PilotMessage, 
    StarAssignmentRequest, 
    WeatherUpdateRequest,
    SpawnRequest,
    CommandType,
    AirportCreateRequest,
    RunwayCreateRequest,
    WaypointCreateRequest,
    WaypointDeleteRequest,
    SimSetAirportRequest
)
from atc_rl_api.api import config_handler

class ConnectionManager:
    """Manages active WebSocket connections for real-time state broadcasting."""
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        # Augment with all available airports for the frontend sidebar
        all_airports = config_handler.list_all_airports()
        # Transform for frontend expectations: { name, lat, lon, runways: [{start, end}] }
        message["airports"] = [
            {
                "name": ap.name,
                "lat": ap.anchor.lat,
                "lon": ap.anchor.lon,
                "runways": [
                    {
                        "start": config_handler.xy_to_latLon_list(rw.start.x, rw.start.y, ap.anchor),
                        "end": config_handler.xy_to_latLon_list(rw.end.x, rw.end.y, ap.anchor)
                    } for rw in ap.runways
                ]
            } for ap in all_airports
        ]
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()
engine = SimulationEngine()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-load Coimbatore if it exists, otherwise just wait
    vocb = config_handler.load_airport_config("VOCB")
    if vocb:
        engine.load_airport(vocb)
    
    task = asyncio.create_task(engine.run(on_step=manager.broadcast))
    yield
    engine.is_active = False
    task.cancel()

app = FastAPI(title="ATC RL API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/state", response_model=FullSimulationState)
async def get_state():
    state = engine.get_full_state()
    # Augment for consistency with broadcast
    all_airports = config_handler.list_all_airports()
    state["airports"] = [
        {
            "name": ap.name,
            "lat": ap.anchor.lat,
            "lon": ap.anchor.lon,
            "runways": [
                {
                    "start": config_handler.xy_to_latLon_list(rw.start.x, rw.start.y, ap.anchor),
                    "end": config_handler.xy_to_latLon_list(rw.end.x, rw.end.y, ap.anchor)
                } for rw in ap.runways
            ]
        } for ap in all_airports
    ]
    return state

@app.post("/reset")
async def reset_simulation():
    engine.reset_environment()
    return {"status": "Simulation reset"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            payload = data.get("payload")
            
            if msg_type == "create_airport":
                # payload: { name, lat, lon }
                from atc_rl_api.api.schemas import AirportCreateRequest
                req = AirportCreateRequest(
                    airport_code=payload["name"][:4].upper(), # Generate code from name
                    name=payload["name"],
                    anchor_lat=payload["lat"],
                    anchor_lon=payload["lon"]
                )
                config_handler.create_airport(req)
                
            elif msg_type == "create_runway":
                # payload: { airport_name, start, end, bidirectional }
                new_cfg = config_handler.add_runway_from_geo(
                    airport_name=payload["airport_name"],
                    start_latlon=payload["start"],
                    end_latlon=payload["end"],
                    bidirectional=payload.get("bidirectional", False)
                )
                if engine.config and engine.config.name == payload["airport_name"]:
                    engine.update_config(new_cfg)
            
            elif msg_type == "delete_runway":
                # payload: { airport_name, runway_id }
                new_cfg = config_handler.delete_runway(payload["airport_name"], payload["runway_id"])
                if new_cfg and engine.config and engine.config.name == payload["airport_name"]:
                    engine.update_config(new_cfg)

            elif msg_type == "delete_aircraft":
                # payload: { callsign }
                engine.remove_aircraft(payload["callsign"])
            
            elif msg_type == "spawn":
                # payload: { gate, callsign?, type?, altitude?, speed? }
                import random
                gate = payload.get("gate", "N")
                callsign = payload.get("callsign", f"SQ{random.randint(100, 999)}")
                ac_type = payload.get("type", "B738")
                altitude = payload.get("altitude", 10000)
                speed = payload.get("speed", 250)
                
                engine.add_aircraft(
                    callsign=callsign,
                    ac_type=ac_type,
                    weight_class="Medium",
                    gate=gate,
                    altitude=altitude,
                    speed=speed
                )
            
            elif msg_type == "command":
                # 1. Handle String Commands (Slash, Natural ATC, or Raw JSON)
                if isinstance(payload, str):
                    payload_trimmed = payload.strip()
                    # A. Slash Commands
                    if payload_trimmed.startswith("/"):
                        if payload_trimmed.startswith("/spawn"):
                            parts = payload_trimmed.split()
                            gate = parts[1].upper() if len(parts) > 1 else "N"
                            import random
                            engine.add_aircraft(
                                callsign=f"SQ{random.randint(100, 999)}",
                                ac_type="B738",
                                weight_class="Medium",
                                gate=gate
                            )
                    # B. Natural ATC String (e.g. "ATC ALTITUDE SQ456 4000")
                    elif payload_trimmed.upper().startswith("ATC "):
                        try:
                            parts = payload_trimmed.split()
                            if len(parts) >= 3:
                                cmd_id = f"ATC_{parts[1].upper()}"
                                callsign = parts[2].upper()
                                value = parts[3] if len(parts) > 3 else None
                                
                                from atc_rl_api.api.schemas import CommandRequest, ATCCommandID, CommandType
                                req_data = {
                                    "type": CommandType.ATC,
                                    "command_id": cmd_id,
                                    "callsign": callsign
                                }
                                
                                if cmd_id == "ATC_ALTITUDE": req_data["new_altitude"] = float(value)
                                elif cmd_id == "ATC_VECTOR": req_data["new_heading"] = float(value)
                                elif cmd_id == "ATC_SPEED": req_data["new_speed"] = float(value)
                                elif cmd_id == "ATC_DIRECT_TO": req_data["waypoint_name"] = value.upper()
                                
                                req = CommandRequest(**req_data)
                                result = await process_command(req)
                                if "error" in result:
                                    print(f"[ATC Parser Error] {result['error']}")
                        except Exception as e:
                            print(f"[ATC Parser Exception] {e}")

                    # C. Raw JSON String
                    elif payload_trimmed.startswith("{"):
                        try:
                            import json
                            cmd_data = json.loads(payload_trimmed)
                            from atc_rl_api.api.schemas import CommandRequest
                            req = CommandRequest(**cmd_data)
                            await process_command(req)
                        except Exception: pass

                # 2. Handle Object Commands (Native JSON from UI)
                elif isinstance(payload, dict):
                    try:
                        from atc_rl_api.api.schemas import CommandRequest
                        req = CommandRequest(**payload)
                        result = await process_command(req)
                        if "error" in result:
                            print(f"[WS Command Error] {result['error']}")
                    except Exception as e:
                        print(f"[WS Command Parse Error] {e}")
                
            elif msg_type == "reset":
                engine.reset_environment()
                print("[Sim Engine] Simulation reset via WebSocket")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WS Error: {e}")
        manager.disconnect(websocket)

# --- Configuration Endpoints ---

@app.post("/config/airport")
async def create_airport(request: AirportCreateRequest):
    config = config_handler.create_airport(request)
    return {"status": "created", "config": config}

@app.post("/config/runway")
async def add_runway(request: RunwayCreateRequest):
    try:
        config = config_handler.add_runway(request)
        return {"status": "updated", "config": config}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/config/waypoint")
async def add_waypoint(request: WaypointCreateRequest):
    try:
        config = config_handler.add_waypoint(request)
        return {"status": "updated", "config": config}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.delete("/config/waypoint")
async def delete_waypoint(request: WaypointDeleteRequest):
    try:
        config = config_handler.delete_waypoint(request)
        return {"status": "updated", "config": config}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# --- Simulation Control ---

@app.post("/sim/set-airport")
async def set_airport(request: SimSetAirportRequest):
    config = config_handler.load_airport_config(request.airport_code)
    if not config:
        raise HTTPException(status_code=404, detail=f"Airport {request.airport_code} not found")
    
    engine.load_airport(config)
    return {"status": "loaded", "airport": request.airport_code}

@app.post("/spawn")
async def spawn_aircraft(request: SpawnRequest):
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
        raise HTTPException(status_code=400, detail="Failed to spawn aircraft (invalid gate or no airport loaded?)")
    return {"status": "Aircraft spawned", "callsign": request.callsign}

async def process_command(request: CommandRequest):
    if request.type == CommandType.SIMULATION:
        if request.command_id == "CMD_SET_TIME_SCALE" and request.time_scale is not None:
            engine.time_scale = request.time_scale
            return {"status": "Time scale updated", "new_scale": engine.time_scale}
        return {"status": "Command received but no matching system logic found"}

    if request.callsign not in engine.aircrafts:
        return {"error": f"Aircraft '{request.callsign}' not found", "code": 404}
        
    aircraft = engine.aircrafts[request.callsign]
    cmd = request.command_id

    # 1. Kinematic Vectoring
    if cmd == "ATC_VECTOR" and request.new_heading is not None:
        aircraft.target_heading = request.new_heading
    elif cmd == "ATC_ALTITUDE" and request.new_altitude is not None:
        aircraft.target_alt = request.new_altitude
    elif cmd == "ATC_SPEED" and request.new_speed is not None:
        aircraft.target_speed = request.new_speed

    # 2. Navigation / State Changes
    elif cmd == "ATC_HOLD":
        aircraft.state = "HOLDING"
        if not aircraft.holding_fix:
             aircraft.holding_fix = {"x": aircraft.x, "y": aircraft.y}
             
    elif cmd == "ATC_RESUME":
        aircraft.state = "ENROUTE"
        aircraft.direct_to_wp = None

    elif cmd == "ATC_DIRECT_TO" and request.waypoint_name:
        if aircraft.active_star and engine.config:
            stars = engine.config.stars.get(aircraft.active_star, {})
            found_wp = None
            for rw_id, wps in stars.items():
                for wp in wps:
                    if wp.name == request.waypoint_name:
                        found_wp = wp.model_dump()
                        break
                if found_wp: break
            
            if found_wp:
                aircraft.direct_to_wp = found_wp
            else:
                 return {"error": f"Waypoint '{request.waypoint_name}' not found", "code": 400}

    elif cmd == "ATC_APPROACH":
        aircraft.state = "APPROACH"
        aircraft.active_star = None
        
    elif cmd == "ATC_LAND":
        aircraft.state = "APPROACH"
        
    return {
        "status": "ATC Command processed", 
        "command_id": cmd,
        "callsign": aircraft.callsign
    }

@app.post("/command")
async def send_command(request: CommandRequest):
    result = await process_command(request)
    if "error" in result:
        raise HTTPException(status_code=result["code"], detail=result["error"])
    return result

@app.post("/update-weather")
async def update_weather(request: WeatherUpdateRequest):
    engine.update_weather(request.wind_heading, request.wind_speed)
    return {
        "status": "Weather updated",
        "active_runway": engine.active_runway,
        "wind_heading": engine.wind_heading,
        "wind_speed": engine.wind_speed
    }
