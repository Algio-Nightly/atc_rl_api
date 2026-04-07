import asyncio
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from atc_rl_api.core.engine import SimulationEngine
from atc_rl_api.api import config_handler
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
    RunwayUpdateRequest,
    SimSetAirportRequest,
    StarRouteSaveRequest,
    LLMCommandRequest
)

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
                "airport_code": ap.airport_code,
                "runways": [
                    {
                        "id": rw.id,
                        "heading": rw.heading,
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
            "airport_code": ap.airport_code,
            "runways": [
                {
                    "id": rw.id,
                    "heading": rw.heading,
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

@app.post("/llm/commands")
async def process_llm_commands(request: LLMCommandRequest):
    """
    Endpoint for LLM/Batch execution of string-based commands.
    Executes each command in sequence.
    """
    results = []
    for cmd_str in request.commands:
        res = await parse_and_process_command_str(cmd_str)
        results.append({"command": cmd_str, "status": res})
    return {"results": results}

async def parse_and_process_command_str(payload: str):
    """
    Parses a raw string command (e.g. 'ATC ALTITUDE SQ123 5000') 
    and routes it to the simulation engine.
    """
    payload_trimmed = payload.strip()
    if not payload_trimmed:
        return "Empty command"
        
    try:
        parts = payload_trimmed.split()
        cmd_prefix = parts[0].upper()
        
        if cmd_prefix == "ATC" and len(parts) >= 3:
            from atc_rl_api.api.schemas import CommandRequest, CommandType
            cmd_id = f"ATC_{parts[1].upper()}"
            callsign = parts[2].upper()
            value = parts[3] if len(parts) > 3 else None
            req_data = {"type": CommandType.ATC, "command_id": cmd_id, "callsign": callsign}
            
            if cmd_id == "ATC_ALTITUDE" and value: req_data["new_altitude"] = float(value)
            elif cmd_id == "ATC_VECTOR" and value: req_data["new_heading"] = float(value)
            elif cmd_id == "ATC_SPEED" and value: req_data["new_speed"] = float(value)
            elif cmd_id == "ATC_DIRECT_TO" and value: req_data["waypoint_name"] = value.upper()
            elif cmd_id == "ATC_HOLD":
                if len(parts) >= 5:
                    # ATC HOLD UA123 POM 5000
                    req_data["waypoint_name"] = parts[3].upper()
                    req_data["new_altitude"] = float(parts[4])
                elif value:
                    req_data["waypoint_name"] = value.upper()
            elif cmd_id == "ATC_LAND" and value:
                req_data["runway_id"] = value.upper()
            elif cmd_id == "ATC_TAXI" and value:
                req_data["runway_id"] = value.upper()
            
            result = await process_command(CommandRequest(**req_data))
            if "error" in result:
                engine.event_buffer.append({"type": "ERROR", "msg": result["error"], "timestamp": time.time()})
                return f"Error: {result['error']}"
            return "Success"
            
        elif cmd_prefix == "SIM" and len(parts) >= 2:
            from atc_rl_api.api.schemas import CommandRequest, CommandType
            sub_cmd = parts[1].upper()
            if sub_cmd == "WIND" and len(parts) >= 4:
                req_data = {
                    "type": CommandType.SIMULATION,
                    "command_id": "CMD_SET_WIND",
                    "wind_heading": float(parts[2]),
                    "wind_speed": float(parts[3])
                }
                await process_command(CommandRequest(**req_data))
            elif sub_cmd == "SCALE" and len(parts) >= 3:
                await process_command(CommandRequest(
                    type=CommandType.SIMULATION,
                    command_id="CMD_SET_TIME_SCALE",
                    time_scale=float(parts[2])
                ))
            return "Success (Sim Command)"
        else:
            err_msg = f"Invalid command format: {payload_trimmed}"
            engine.event_buffer.append({"type": "ERROR", "msg": err_msg, "timestamp": time.time()})
            return err_msg
            
    except Exception as e:
        err_msg = f"Command Error: {str(e)}"
        print(f"[ATC/SIM Parser Error] {err_msg}")
        engine.event_buffer.append({"type": "ERROR", "msg": err_msg, "timestamp": time.time()})
        return err_msg

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    
    # 1. Immediate Initial Sync (Replaces /state)
    state = engine.get_full_state()
    # Augment with airports list
    all_airports = config_handler.list_all_airports()
    state["airports"] = [
        {
            "name": ap.name,
            "lat": ap.anchor.lat,
            "lon": ap.anchor.lon,
            "airport_code": ap.airport_code,
            "runways": [
                {
                    "id": rw.id,
                    "heading": rw.heading,
                    "start": config_handler.xy_to_latLon_list(rw.start.x, rw.start.y, ap.anchor),
                    "end": config_handler.xy_to_latLon_list(rw.end.x, rw.end.y, ap.anchor)
                } for rw in ap.runways
            ]
        } for ap in all_airports
    ]
    await websocket.send_json(state)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            payload = data.get("payload", {})
            
            try:
                if msg_type == "create_airport":
                    from atc_rl_api.api.schemas import AirportCreateRequest
                    req = AirportCreateRequest(
                        airport_code=payload.get("name", "UNKN")[:4].upper(),
                        name=payload.get("name", "Unknown"),
                        anchor_lat=payload.get("lat", 0),
                        anchor_lon=payload.get("lon", 0)
                    )
                    config_handler.create_airport(req)
                    engine.event_buffer.append({"type": "AIRPORT_CREATED", "name": req.name, "code": req.airport_code, "timestamp": time.time()})
                    print(f"[Sim Engine] Airport Created: {req.name}")
                    
                elif msg_type == "create_runway":
                    ap_code = payload.get("airport_code")
                    if not ap_code:
                        ap_name = payload.get("airport_name")
                        all_ap = config_handler.list_all_airports()
                        target = next((a for a in all_ap if a.name == ap_name), None)
                        ap_code = target.airport_code if target else "VOCB"

                    new_cfg = config_handler.add_runway_from_geo(
                        airport_code=ap_code,
                        start_latlon=payload.get("start"),
                        end_latlon=payload.get("end"),
                        bidirectional=payload.get("bidirectional", False)
                    )
                    rw_id = payload.get("runway_id") or "NEW_RWY"
                    engine.event_buffer.append({"type": "RUNWAY_CREATED", "id": rw_id, "timestamp": time.time()})
                    if engine.config and engine.config.airport_code == ap_code:
                        engine.update_config(new_cfg)

                elif msg_type == "create_waypoint":
                    from atc_rl_api.api.schemas import WaypointCreateRequest
                    ap_code = payload.get("airport_code")
                    if not ap_code:
                        ap_name = payload.get("airport_name")
                        all_ap = config_handler.list_all_airports()
                        target = next((a for a in all_ap if a.name == ap_name), None)
                        ap_code = target.airport_code if target else "VOCB"

                    req = WaypointCreateRequest(
                        airport_code=ap_code,
                        x=payload.get("x"),
                        y=payload.get("y"),
                        name=payload.get("name"),
                        target_alt=payload.get("target_alt"),
                        target_speed=payload.get("target_speed"),
                        is_iaf=payload.get("is_iaf", False)
                    )
                    new_cfg = config_handler.add_waypoint(req)
                    engine.event_buffer.append({"type": "WAYPOINT_CREATED", "name": req.name or "WP", "timestamp": time.time()})
                    if engine.config and engine.config.airport_code == req.airport_code:
                        engine.update_config(new_cfg)

                elif msg_type == "save_star_route":
                    ap_code = payload.get("airport_code")
                    if not ap_code:
                        ap_name = payload.get("airport_name")
                        all_ap = config_handler.list_all_airports()
                        target = next((a for a in all_ap if a.name == ap_name), None)
                        ap_code = target.airport_code if target else "VOCB"
                        
                    req = StarRouteSaveRequest(
                        airport_code=ap_code,
                        gate_id=payload.get("gate"),
                        runway_id=payload.get("runway_id"),
                        route_sequence=payload.get("sequence", [])
                    )
                    new_cfg = config_handler.save_star_route(req)
                    if engine.config and engine.config.airport_code == req.airport_code:
                        engine.update_config(new_cfg)

                elif msg_type == "update_waypoint":
                    from atc_rl_api.api.schemas import WaypointUpdateRequest
                    ap_code = payload.get("airport_code")
                    if not ap_code:
                        ap_name = payload.get("airport_name")
                        all_ap = config_handler.list_all_airports()
                        target = next((a for a in all_ap if a.name == ap_name), None)
                        ap_code = target.airport_code if target else "VOCB"
                        
                    req = WaypointUpdateRequest(
                        airport_code=ap_code,
                        # Support multiple keys for waypoint ID to be extra safe
                        waypoint_id=payload.get("waypoint_id") or payload.get("id") or payload.get("wp_id"),
                        gate_id=payload.get("gate"),
                        target_runway=payload.get("runway_id"),
                        sequence_index=payload.get("index"),
                        name=payload.get("name"),
                        target_alt=payload.get("target_alt"),
                        target_speed=payload.get("target_speed")
                    )
                    new_cfg = config_handler.update_waypoint(req)
                    if engine.config and engine.config.airport_code == req.airport_code:
                        engine.update_config(new_cfg)
                
                elif msg_type == "delete_waypoint":
                    wp_id = payload.get("waypoint_id")
                    ap_code = payload.get("airport_code") or "VOCB"
                    if ap_code and wp_id:
                        new_cfg = config_handler.delete_waypoint(ap_code, wp_id)
                        if new_cfg and engine.config and engine.config.airport_code == ap_code:
                            engine.update_config(new_cfg)

                elif msg_type == "update_runway":
                    from atc_rl_api.api.schemas import RunwayUpdateRequest
                    ap_code = payload.get("airport_code")
                    if not ap_code: 
                        ap_name = payload.get("airport_name")
                        all_ap = config_handler.list_all_airports()
                        target = next((a for a in all_ap if a.name == ap_name), None)
                        ap_code = target.airport_code if target else "VOCB"

                    req = RunwayUpdateRequest(
                        airport_code=ap_code,
                        runway_id=payload.get("runway_id"),
                        new_id=payload.get("new_id"),
                        heading=payload.get("heading")
                    )
                    new_cfg = config_handler.update_runway(req)
                    if engine.config and engine.config.airport_code == req.airport_code:
                        engine.update_config(new_cfg)

                elif msg_type == "delete_runway":
                    ap_code = payload.get("airport_code")
                    if not ap_code:
                        ap_name = payload.get("airport_name")
                        all_ap = config_handler.list_all_airports()
                        target = next((a for a in all_ap if a.name == ap_name), None)
                        ap_code = target.airport_code if target else "VOCB"
                        
                    rw_id = payload.get("runway_id")
                    if ap_code and rw_id:
                        new_cfg = config_handler.delete_runway(ap_code, rw_id)
                        if new_cfg and engine.config and engine.config.airport_code == ap_code:
                            engine.update_config(new_cfg)

                elif msg_type == "delete_aircraft":
                    callsign = payload.get("callsign", "").upper()
                    if callsign:
                        engine.remove_aircraft(callsign)
                
                elif msg_type == "spawn":
                    import random
                    is_departure = str(payload.get("is_departure", "false")).lower() == "true"
                    gate = payload.get("gate", "N")
                    callsign = payload.get("callsign", f"SQ{random.randint(100, 999)}").upper()
                    ac_type = payload.get("type", "B738")
                    
                    if is_departure:
                        rw_id = payload.get("runway_id")
                        if not rw_id:
                            rw_id = engine.active_runways[0] if engine.active_runways else "RWY_1"
                        term_gate = payload.get("terminal_gate_id")
                        print(f"[API] Spawning DEPARTURE: {callsign} on {rw_id} via {gate} (Terminal Gate: {term_gate or 'Default'})")
                        engine.spawn_departure(callsign, ac_type, rw_id, gate, term_gate)
                    else:
                        print(f"[API] Spawning ARRIVAL: {callsign} via {gate}")
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
                
                elif msg_type == "update_weather":
                    from atc_rl_api.api.schemas import WeatherUpdateRequest
                    req = WeatherUpdateRequest(**payload)
                    engine.update_weather(req.wind_heading, req.wind_speed)
                    print(f"[Sim Engine] Weather updated: {req.wind_heading}° @ {req.wind_speed}kts")
                
                elif msg_type == "command":
                    if isinstance(payload, str):
                        await parse_and_process_command_str(payload)
                    elif isinstance(payload, dict):
                        from atc_rl_api.api.schemas import CommandRequest
                        await process_command(CommandRequest(**payload))
                    
                elif msg_type == "shutdown":
                    print("[Sim Engine] Shutdown requested via WebSocket. Exiting...")
                    import os
                    import signal
                    os.kill(os.getpid(), signal.SIGINT)

                elif msg_type == "select_airport":
                    ap_code = payload.get("code") or payload.get("airport_code")
                    if not ap_code:
                        ap_name = payload.get("name")
                        all_ap = config_handler.list_all_airports()
                        target = next((a for a in all_ap if a.name == ap_name), None)
                        ap_code = target.airport_code if target else None
                    
                    if ap_code:
                        config = config_handler.load_airport_config(ap_code)
                        if config:
                            engine.load_airport(config)
                            print(f"[Sim Engine] Active airport changed to: {config.name} ({ap_code})")

                elif msg_type == "reset":
                    engine.reset_environment()
                    print("[Sim Engine] Simulation reset via WebSocket")

                elif msg_type == "set_time_scale":
                    new_scale = float(payload.get("scale", 1.0))
                    engine.time_scale = new_scale
                    if engine.config:
                        engine.config.time_scale = new_scale
                        config_handler.save_airport_config(engine.config)
                    print(f"[Sim Engine] Time scale updated to {new_scale}x and persisted.")

            except Exception as e:
                print(f"[WS Handler Error] type={msg_type}, error={e}")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WS Critical Loop Error: {e}")
        manager.disconnect(websocket)

# --- Simulation Control Functions ---

async def process_command(request: CommandRequest):
    if request.type == CommandType.SIMULATION:
        if request.command_id == "CMD_SET_TIME_SCALE" and request.time_scale is not None:
            engine.time_scale = request.time_scale
            if engine.config:
                engine.config.time_scale = request.time_scale
                config_handler.save_airport_config(engine.config)
            engine.event_buffer.append({"type": "INFO", "msg": f"CMD: Time scale set to {request.time_scale}x (Persisted)", "timestamp": time.time()})
            return {"status": "Time scale updated"}
        elif request.command_id == "CMD_SET_WIND" and request.wind_heading is not None:
            engine.update_weather(request.wind_heading, request.wind_speed or engine.wind_speed)
            engine.event_buffer.append({"type": "INFO", "msg": f"CMD: Wind updated to {request.wind_heading}° @ {request.wind_speed or engine.wind_speed}kts", "timestamp": time.time()})
            return {"status": "Wind updated"}
        return {"status": "Command received"}

    if request.callsign not in engine.aircrafts:
        return {"error": f"Aircraft '{request.callsign}' not found", "code": 404}
        
    aircraft = engine.aircrafts[request.callsign]
    cmd = request.command_id

    if cmd == "ATC_VECTOR" and request.new_heading is not None:
        aircraft.target_heading = request.new_heading
        engine.event_buffer.append({"type": "ATC", "msg": f"HEADING: {request.callsign} -> {request.new_heading}°", "timestamp": time.time()})
    elif cmd == "ATC_ALTITUDE" and request.new_altitude is not None:
        aircraft.target_alt = request.new_altitude
        engine.event_buffer.append({"type": "ATC", "msg": f"ALTITUDE: {request.callsign} -> {request.new_altitude}ft", "timestamp": time.time()})
    elif cmd == "ATC_SPEED" and request.new_speed is not None:
        aircraft.target_speed = request.new_speed
        engine.event_buffer.append({"type": "ATC", "msg": f"SPEED: {request.callsign} -> {request.new_speed}kts", "timestamp": time.time()})
    elif cmd == "ATC_HOLD":
        if request.waypoint_name and engine.config:
            # 1. Flexible search for the holding waypoint
            search_term = request.waypoint_name.upper()
            found_wp = None
            for wp in engine.config.waypoints.values():
                if (wp.name and wp.name.upper() == search_term) or wp.id.upper() == search_term:
                    found_wp = wp.model_dump()
                    break
            
            if found_wp:
                aircraft.holding_fix = {"x": found_wp["x"], "y": found_wp["y"]}
                if request.new_altitude is not None:
                    aircraft.target_alt = request.new_altitude
                aircraft.state = "HOLDING"
                
                msg = f"HOLD: {request.callsign} holding at {found_wp['name']}"
                if request.new_altitude is not None:
                    msg += f" @ {int(request.new_altitude)}ft"
                engine.event_buffer.append({"type": "ATC", "msg": msg, "timestamp": time.time()})
            else:
                return {"error": f"Holding waypoint '{request.waypoint_name}' not found", "code": 404}
        else:
            # Fallback for simple HOLD commands
            aircraft.state = "HOLDING"
            if not aircraft.holding_fix: aircraft.holding_fix = {"x": aircraft.x, "y": aircraft.y}
            engine.event_buffer.append({"type": "ATC", "msg": f"HOLD: {request.callsign} holding current position", "timestamp": time.time()})
    elif cmd == "ATC_RESUME":
        aircraft.state = "ENROUTE"
        aircraft.direct_to_wp = None
        engine.event_buffer.append({"type": "ATC", "msg": f"RESUME: {request.callsign} resuming standard navigation", "timestamp": time.time()})
    elif cmd == "ATC_DIRECT_TO" and request.waypoint_name:
        if engine.config:
            # 1. Flexible search by Name or ID (Case-Insensitive)
            search_term = request.waypoint_name.upper()
            found_wp = None
            for wp in engine.config.waypoints.values():
                if (wp.name and wp.name.upper() == search_term) or wp.id.upper() == search_term:
                    found_wp = wp.model_dump()
                    break
            
            if found_wp: 
                aircraft.direct_to_wp = found_wp
                # Ensure we jump to ENROUTE state to prioritize this waypoint
                aircraft.state = "ENROUTE" 
                engine.event_buffer.append({"type": "ATC", "msg": f"DIRECT: {request.callsign} proceeding to {found_wp['name']}", "timestamp": time.time()})
            else:
                return {"error": f"Waypoint '{request.waypoint_name}' not found in airport pool", "code": 404}
    elif cmd == "ATC_APPROACH":
        # Validation: Check if runway is busy
        rw_id = request.runway_id or (engine.active_runways[0] if engine.active_runways else None)
        if rw_id:
            status_obj = engine.get_full_state()["runway_status"].get(rw_id.upper())
            if status_obj and status_obj["status"] != "CLEAR" and status_obj["reserved_by"] != request.callsign:
                return {"error": f"Runway {rw_id} is currently {status_obj['status']} ({status_obj.get('occupied_by') or status_obj.get('reserved_by') or 'Cooldown'})", "code": 409}

        aircraft.state = "APPROACH"
        aircraft.active_star = None
        engine.event_buffer.append({"type": "ATC", "msg": f"CLEARED: {request.callsign} cleared for immediate approach", "timestamp": time.time()})
    elif cmd == "ATC_LAND":
        if request.runway_id and engine.config:
            # 1. Validation: Does runway exist?
            rw_id = request.runway_id.upper()
            target_rw = next((r for r in engine.config.runways if r.id == rw_id), None)
            
            if not target_rw:
                return {"error": f"Runway '{rw_id}' not found in configuration", "code": 404}
            
            # 2. Safety Check: Is the runway busy or reserved for someone else?
            # We call engine.get_full_state() to get the dynamic status
            status_obj = engine.get_full_state()["runway_status"].get(rw_id)
            if status_obj and status_obj["status"] != "CLEAR" and status_obj["reserved_by"] != request.callsign:
                return {"error": f"Runway {rw_id} is currently {status_obj['status']} ({status_obj.get('occupied_by') or status_obj.get('reserved_by') or 'Cooling Down'})", "code": 409}

            # 3. Queue the Landing
            aircraft.queued_landing = {
                "runway_id": rw_id,
                "threshold": {"x": target_rw.start.x, "y": target_rw.start.y},
                "runway_heading": target_rw.heading
            }
            
            engine.event_buffer.append({"type": "ATC", "msg": f"QUEUED: {request.callsign} cleared for landing Runway {rw_id} (Arrival sequence will be completed first)", "timestamp": time.time()})
        else:
            return {"error": "ATC_LAND requires runway_id", "code": 400}
    elif cmd == "ATC_TAXI":
        if aircraft.state != "ON_GATE":
            return {"error": f"Aircraft must be ON_GATE to receive taxi clearance. Current state: {aircraft.state}", "code": 400}
        
        if request.runway_id:
            rw_id = request.runway_id.upper()
            target_rw = next((r for r in engine.config.runways if r.id == rw_id), None)
            if not target_rw:
                return {"error": f"Runway {rw_id} not found", "code": 404}
            
            aircraft.target_runway_id = rw_id
            aircraft.runway_threshold = {"x": target_rw.start.x, "y": target_rw.start.y}
            aircraft.runway_heading = target_rw.heading
            
        aircraft.state = "TAXIING"
        engine.event_buffer.append({"type": "ATC", "msg": f"TAXIING: {request.callsign} taxi to Runway {aircraft.target_runway_id}", "timestamp": time.time()})
    elif cmd == "ATC_LINE_UP":
        # 1. Safety Check: Is the runway busy?
        if not aircraft.target_runway_id:
            return {"error": "Aircraft has no assigned departure runway", "code": 400}
        
        rw_id = aircraft.target_runway_id
        status_obj = engine.get_full_state()["runway_status"].get(rw_id)
        if status_obj and status_obj["status"] != "CLEAR" and status_obj["reserved_by"] != request.callsign:
            return {"error": f"Runway {rw_id} is currently {status_obj['status']} ({status_obj.get('occupied_by') or status_obj.get('reserved_by') or 'Cooldown'})", "code": 409}

        # 2. Claim the lock
        engine.runway_status[rw_id]["occupied_by"] = request.callsign
        aircraft.state = "LINE_UP"
        engine.event_buffer.append({"type": "ATC", "msg": f"LINE-UP: {request.callsign} lining up Runway {rw_id}", "timestamp": time.time()})
        
    elif cmd == "ATC_TAKEOFF":
        if aircraft.state not in ["LINE_UP", "HOLDING_SHORT"]:
            return {"error": f"Aircraft must be LINED UP or HOLDING SHORT before takeoff. Current state: {aircraft.state}", "code": 400}
        
        rw_id = aircraft.target_runway_id
        if not rw_id:
            return {"error": "Aircraft has no assigned departure runway", "code": 400}

        if aircraft.state == "HOLDING_SHORT":
            # 1. Safety Check: Is the runway busy?
            status_obj = engine.get_full_state()["runway_status"].get(rw_id)
            if status_obj and status_obj["status"] != "CLEAR" and status_obj["reserved_by"] != request.callsign:
                return {"error": f"Runway {rw_id} is currently {status_obj['status']} ({status_obj.get('occupied_by') or status_obj.get('reserved_by') or 'Cooldown'})", "code": 409}

            # 2. Automation: Start line-up with timer
            aircraft.state = "LINE_UP"
            aircraft.line_up_timer = 30.0
            engine.runway_status[rw_id]["occupied_by"] = request.callsign
            engine.event_buffer.append({"type": "ATC", "msg": f"LINE-UP & WAIT: {request.callsign} entering Runway {rw_id} (Alignment: 30s)", "timestamp": time.time()})
        else:
            # Already lined up, immediate takeoff
            aircraft.state = "TAKEOFF_ROLL"
            engine.event_buffer.append({"type": "ATC", "msg": f"CLEARED FOR TAKEOFF: {request.callsign} Runway {rw_id}", "timestamp": time.time()})
        
    return {"status": "ATC Command processed"}
