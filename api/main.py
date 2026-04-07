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
    results = []
    for cmd_str in request.commands:
        res = await parse_and_process_command_str(cmd_str)
        results.append({"command": cmd_str, "status": res})
    return {"results": results}

async def parse_and_process_command_str(payload: str):
    payload_trimmed = payload.strip()
    if not payload_trimmed:
        return "Empty command"
        
    try:
        parts = payload_trimmed.split()
        cmd_prefix = parts[0].upper()
        if cmd_prefix == "ATC" and len(parts) >= 3:
            from atc_rl_api.api.schemas import CommandRequest, CommandType
            sub_id = parts[1].upper()
            cmd_id = f"ATC_{sub_id}"
            
            if sub_id == "DIRECT" and len(parts) >= 5 and parts[3].upper() == "TO":
                callsign = parts[2].upper()
                value = parts[4].upper()
                cmd_id = "ATC_DIRECT_TO"
                req_data = {"type": CommandType.ATC, "command_id": cmd_id, "callsign": callsign, "waypoint_name": value}
            else:
                callsign = parts[2].upper()
                value = parts[3] if len(parts) > 3 else None
                req_data = {"type": CommandType.ATC, "command_id": cmd_id, "callsign": callsign}
            
            if cmd_id == "ATC_ALTITUDE" and value: req_data["new_altitude"] = float(value)
            elif cmd_id == "ATC_SPEED" and value: req_data["new_speed"] = float(value)
            elif cmd_id == "ATC_DIRECT_TO" and value: req_data["waypoint_name"] = value.upper()
            elif cmd_id == "ATC_HOLD":
                if len(parts) >= 5:
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
                req_data = {"type": CommandType.SIMULATION, "command_id": "CMD_SET_WIND", "wind_heading": float(parts[2]), "wind_speed": float(parts[3])}
                await process_command(CommandRequest(**req_data))
            elif sub_cmd == "SCALE" and len(parts) >= 3:
                await process_command(CommandRequest(type=CommandType.SIMULATION, command_id="CMD_SET_TIME_SCALE", time_scale=float(parts[2])))
            return "Success (Sim Command)"
    except Exception as e:
        err_msg = f"Command Error: {str(e)}"
        engine.event_buffer.append({"type": "ERROR", "msg": err_msg, "timestamp": time.time()})
        return err_msg

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    state = engine.get_full_state()
    all_airports = config_handler.list_all_airports()
    state["airports"] = [{"name": ap.name, "lat": ap.anchor.lat, "lon": ap.anchor.lon, "airport_code": ap.airport_code, "runways": [{"id": rw.id, "heading": rw.heading, "start": config_handler.xy_to_latLon_list(rw.start.x, rw.start.y, ap.anchor), "end": config_handler.xy_to_latLon_list(rw.end.x, rw.end.y, ap.anchor)} for rw in ap.runways]} for ap in all_airports]
    await websocket.send_json(state)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type, payload = data.get("type"), data.get("payload", {})
            try:
                if msg_type == "create_airport":
                    from atc_rl_api.api.schemas import AirportCreateRequest
                    req = AirportCreateRequest(airport_code=payload.get("name", "UNKN")[:4].upper(), name=payload.get("name", "Unknown"), anchor_lat=payload.get("lat", 0), anchor_lon=payload.get("lon", 0))
                    config_handler.create_airport(req)
                    engine.event_buffer.append({"type": "AIRPORT_CREATED", "name": req.name, "code": req.airport_code, "timestamp": time.time()})
                elif msg_type == "create_runway":
                    ap_code = payload.get("airport_code") or "VOCB"
                    new_cfg = config_handler.add_runway_from_geo(airport_code=ap_code, start_latlon=payload.get("start"), end_latlon=payload.get("end"), bidirectional=payload.get("bidirectional", False))
                    if engine.config and engine.config.airport_code == ap_code: engine.update_config(new_cfg)
                elif msg_type == "create_waypoint":
                    ap_code = payload.get("airport_code") or "VOCB"
                    from atc_rl_api.api.schemas import WaypointCreateRequest
                    req = WaypointCreateRequest(airport_code=ap_code, x=payload.get("x"), y=payload.get("y"), name=payload.get("name"), target_alt=payload.get("target_alt"), target_speed=payload.get("target_speed"), is_iaf=payload.get("is_iaf", False))
                    new_cfg = config_handler.add_waypoint(req)
                    if engine.config and engine.config.airport_code == ap_code: engine.update_config(new_cfg)
                elif msg_type == "save_star_route":
                    ap_code = payload.get("airport_code") or "VOCB"
                    from atc_rl_api.api.schemas import StarRouteSaveRequest
                    req = StarRouteSaveRequest(airport_code=ap_code, gate_id=payload.get("gate"), runway_id=payload.get("runway_id"), route_sequence=payload.get("sequence", []), name=payload.get("name"))
                    new_cfg = config_handler.save_star_route(req)
                    if engine.config and engine.config.airport_code == ap_code: engine.update_config(new_cfg)
                elif msg_type == "save_sid_route":
                    ap_code = payload.get("airport_code") or "VOCB"
                    from atc_rl_api.api.schemas import SidRouteSaveRequest
                    req = SidRouteSaveRequest(airport_code=ap_code, runway_id=payload.get("runway_id"), gate_id=payload.get("gate"), route_sequence=payload.get("sequence", []), name=payload.get("name"))
                    new_cfg = config_handler.save_sid_route(req)
                    if engine.config and engine.config.airport_code == ap_code: engine.update_config(new_cfg)
                elif msg_type == "update_waypoint":
                    ap_code = payload.get("airport_code") or "VOCB"
                    from atc_rl_api.api.schemas import WaypointUpdateRequest
                    req = WaypointUpdateRequest(airport_code=ap_code, waypoint_id=payload.get("waypoint_id"), name=payload.get("name"), target_alt=payload.get("target_alt"), target_speed=payload.get("target_speed"))
                    new_cfg = config_handler.update_waypoint(req)
                    if engine.config and engine.config.airport_code == ap_code: engine.update_config(new_cfg)
                elif msg_type == "delete_waypoint":
                    ap_code, wp_id = payload.get("airport_code") or "VOCB", payload.get("waypoint_id")
                    if wp_id:
                        new_cfg = config_handler.delete_waypoint(ap_code, wp_id)
                        if engine.config and engine.config.airport_code == ap_code: engine.update_config(new_cfg)
                elif msg_type == "update_runway":
                    ap_code = payload.get("airport_code") or "VOCB"
                    from atc_rl_api.api.schemas import RunwayUpdateRequest
                    req = RunwayUpdateRequest(airport_code=ap_code, runway_id=payload.get("runway_id"), new_id=payload.get("new_id"), heading=payload.get("heading"))
                    new_cfg = config_handler.update_runway(req)
                    if engine.config and engine.config.airport_code == ap_code: engine.update_config(new_cfg)
                elif msg_type == "delete_runway":
                    ap_code, rw_id = payload.get("airport_code") or "VOCB", payload.get("runway_id")
                    if rw_id:
                        new_cfg = config_handler.delete_runway(ap_code, rw_id)
                        if engine.config and engine.config.airport_code == ap_code: engine.update_config(new_cfg)
                elif msg_type == "shutdown":
                    import os, signal
                    os.kill(os.getpid(), signal.SIGINT)
                elif msg_type == "command":
                    if isinstance(payload, str): await parse_and_process_command_str(payload)
                    elif isinstance(payload, dict): await process_command(CommandRequest(**payload))
                elif msg_type == "spawn":
                    import random
                    is_departure = str(payload.get("is_departure", "false")).lower() == "true"
                    gate, callsign, ac_type = payload.get("gate", "N"), payload.get("callsign", f"SQ{random.randint(100, 999)}").upper(), payload.get("type", "B738")
                    if is_departure: engine.spawn_departure(callsign, ac_type, payload.get("runway_id") or "RWY_1", gate, payload.get("terminal_gate_id"))
                    else: engine.add_aircraft(callsign, ac_type, "Medium", gate, payload.get("altitude", 10000), payload.get("speed", 250))
                elif msg_type == "select_airport":
                    ap_code = payload.get("code") or payload.get("airport_code")
                    if ap_code: 
                        config = config_handler.load_airport_config(ap_code)
                        if config: engine.load_airport(config)
                elif msg_type == "reset": engine.reset_environment()
                elif msg_type == "set_time_scale":
                    new_scale = float(payload.get("scale", 1.0))
                    engine.time_scale = new_scale
                    if engine.config: 
                        engine.config.time_scale = new_scale
                        config_handler.save_airport_config(engine.config)
            except Exception as e: print(f"[WS Handler Error] {e}")
    except WebSocketDisconnect: manager.disconnect(websocket)
    except Exception as e: manager.disconnect(websocket)

async def process_command(request: CommandRequest):
    if request.type == CommandType.SIMULATION:
        if request.command_id == "CMD_SET_TIME_SCALE" and request.time_scale is not None:
            engine.time_scale = request.time_scale
            if engine.config: 
                engine.config.time_scale = request.time_scale
                config_handler.save_airport_config(engine.config)
            return {"status": "Time scale updated"}
        return {"status": "Command received"}
    if request.callsign not in engine.aircrafts: return {"error": f"Aircraft '{request.callsign}' not found", "code": 404}
    aircraft, cmd = engine.aircrafts[request.callsign], request.command_id
    if cmd == "ATC_ALTITUDE" and request.new_altitude is not None:
        alt = max(100.0, min(45000.0, float(request.new_altitude)))
        aircraft.manual_target_alt = aircraft.target_alt = alt
        engine.event_buffer.append({"type": "ATC", "msg": f"ALTITUDE: {request.callsign} -> {alt}ft (manual)", "timestamp": time.time()})
    elif cmd == "ATC_SPEED" and request.new_speed is not None:
        spd = max(140.0, min(450.0, float(request.new_speed)))
        aircraft.manual_target_speed = aircraft.target_speed = spd
        engine.event_buffer.append({"type": "ATC", "msg": f"SPEED: {request.callsign} -> {spd}kts (manual)", "timestamp": time.time()})
    elif cmd == "ATC_DIRECT_TO" and request.waypoint_name:
        if engine.config:
            search_term = request.waypoint_name.upper()
            # 1. Check for STAR Procedures
            for key, name in engine.config.star_names.items():
                if name.upper() == search_term:
                    gate_id, rwy_id = key.split(":")
                    if gate_id in engine.config.stars and rwy_id in engine.config.stars[gate_id]:
                        aircraft.active_star, aircraft.wp_index, aircraft.target_runway_id, aircraft.state = gate_id, 0, rwy_id, "ENROUTE"
                        engine.event_buffer.append({"type": "ATC", "msg": f"DIRECT: {request.callsign} proc {name} for RWY {rwy_id}", "timestamp": time.time()})
                        return {"status": "success"}
            
            # 2. Check for SID Procedures
            for key, name in engine.config.sid_names.items():
                if name.upper() == search_term:
                    rwy_id, gate_id = key.split(":")
                    sid_wp_ids = engine.config.sids.get(rwy_id, {}).get(gate_id, [])
                    if sid_wp_ids:
                        route = []
                        for wp_id in sid_wp_ids:
                            wp = engine.config.waypoints.get(wp_id)
                            if wp: route.append(wp.model_dump())
                            elif wp_id in engine.config.gates:
                                gp = engine.config.gates[wp_id]
                                route.append({"id": wp_id, "name": wp_id, "x": gp.x, "y": gp.y, "target_alt": 6000, "target_speed": 250})
                        aircraft.active_route, aircraft.route_index, aircraft.state = route, 0, "CLIMB_OUT"
                        engine.event_buffer.append({"type": "ATC", "msg": f"DIRECT: {request.callsign} sid {name} to {gate_id}", "timestamp": time.time()})
                        return {"status": "success"}

            # 3. Check for Individual Waypoints
            found_wp = next((wp for wp in engine.config.waypoints.values() if (wp.name and wp.name.upper() == search_term) or wp.id.upper() == search_term), None)
            if found_wp:
                aircraft.direct_to_wp = found_wp.model_dump()
                # If we are on a STAR, try to skip ahead in the sequence
                if aircraft.active_star and aircraft.active_star in engine.config.stars:
                    # We need to find which runway we are targeting to get the list of WP IDs
                    rwy_id = aircraft.target_runway_id or list(engine.config.stars[aircraft.active_star].keys())[0]
                    route_ids = engine.config.stars[aircraft.active_star].get(rwy_id, [])
                    try: 
                        aircraft.wp_index = route_ids.index(found_wp.id) + 1
                    except ValueError: pass
                aircraft.state = "ENROUTE"
                engine.event_buffer.append({"type": "ATC", "msg": f"DIRECT: {request.callsign} to {found_wp.name}", "timestamp": time.time()})
                return {"status": "success"}
            return {"error": f"Target '{request.waypoint_name}' not found", "code": 404}
    elif cmd == "ATC_RESUME":
        aircraft.state, aircraft.direct_to_wp = "ENROUTE", None
        aircraft.manual_target_alt = aircraft.manual_target_speed = None
        engine.event_buffer.append({"type": "ATC", "msg": f"RESUME: {request.callsign} (manual overrides cleared)", "timestamp": time.time()})
    elif cmd == "ATC_LAND":
        if request.runway_id and engine.config:
            rw_id = request.runway_id.upper()
            target_rw = next((r for r in engine.config.runways if r.id == rw_id), None)
            if not target_rw: return {"error": f"Runway {rw_id} not found", "code": 404}
            entry_gate = aircraft.gate or "N"
            new_route, msg_suffix = engine.config.stars.get(entry_gate, {}).get(rw_id), ""
            if new_route:
                aircraft.active_star, aircraft.wp_index = entry_gate, 0
                msg_suffix = f" via {engine.config.star_names.get(f'{entry_gate}:{rw_id}', 'STD')}"
            aircraft.queued_landing = {"runway_id": rw_id, "threshold": {"x": target_rw.start.x, "y": target_rw.start.y}, "runway_heading": target_rw.heading}
            engine.event_buffer.append({"type": "ATC", "msg": f"CLEARED LAND: {request.callsign} RWY {rw_id}{msg_suffix}", "timestamp": time.time()})
        else: return {"error": "Missing runway_id", "code": 400}
    elif cmd == "ATC_TAXI":
        if aircraft.state != "ON_GATE": return {"error": "Must be ON_GATE", "code": 400}
        if request.runway_id:
            rw_id = request.runway_id.upper()
            target_rw = next((r for r in engine.config.runways if r.id == rw_id), None)
            if target_rw: aircraft.target_runway_id, aircraft.runway_threshold, aircraft.runway_heading = rw_id, {"x": target_rw.start.x, "y": target_rw.start.y}, target_rw.heading
        aircraft.state = "TAXIING"
        engine.event_buffer.append({"type": "ATC", "msg": f"TAXI: {request.callsign} to RWY {aircraft.target_runway_id}", "timestamp": time.time()})
    elif cmd == "ATC_LINE_UP":
        if not aircraft.target_runway_id: return {"error": "No runway assigned", "code": 400}
        aircraft.state = "LINE_UP"
        engine.runway_status[aircraft.target_runway_id]["occupied_by"] = request.callsign
        engine.event_buffer.append({"type": "ATC", "msg": f"LINE-UP: {request.callsign} RWY {aircraft.target_runway_id}", "timestamp": time.time()})
    elif cmd == "ATC_TAKEOFF":
        if aircraft.state not in ["LINE_UP", "HOLDING_SHORT"]: return {"error": "Incorrect state", "code": 400}
        aircraft.state = "TAKEOFF_ROLL"
        engine.event_buffer.append({"type": "ATC", "msg": f"CLEARED TAKEOFF: {request.callsign}", "timestamp": time.time()})
    return {"status": "success"}
