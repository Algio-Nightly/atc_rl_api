import os
import json
import math
import random
from pathlib import Path
from typing import Optional, List
from atc_rl_api.api.schemas import (
    AirportConfig, RunwayConfig, Point, LatLon, 
    AirportCreateRequest, RunwayCreateRequest, 
    WaypointCreateRequest, WaypointDeleteRequest,
    WaypointUpdateRequest, RunwayUpdateRequest,
    WaypointConfig, StarRouteSaveRequest
)

# Calculate AIRPORTS_DIR relative to this file's location (atc_rl_api/api/config_handler.py)
AIRPORTS_DIR = Path(__file__).parent.parent / "airports"
AIRPORTS_DIR.mkdir(parents=True, exist_ok=True)

def get_airport_path(airport_code: str) -> Path:
    return AIRPORTS_DIR / f"{airport_code.upper()}.json"

def load_airport_config(airport_code: str) -> Optional[AirportConfig]:
    path = get_airport_path(airport_code)
    if not path.exists():
        return None
    with open(path, "r") as f:
        data = json.load(f)
        return AirportConfig(**data)

def save_airport_config(config: AirportConfig):
    path = get_airport_path(config.airport_code)
    with open(path, "w") as f:
        # Pydantic's .model_dump() for serialization
        json.dump(config.model_dump(), f, indent=2)

def create_airport(req: AirportCreateRequest) -> AirportConfig:
    # 100x100km setup
    width = 100.0
    height = 100.0
    center_x = width / 2.0
    center_y = height / 2.0
    
    config = AirportConfig(
        airport_code=req.airport_code.upper(),
        name=req.name,
        anchor=LatLon(lat=req.anchor_lat, lon=req.anchor_lon),
        bounds={"width_km": 100.0, "height_km": 100.0},
        center=Point(x=0, y=0),
        gates={
            "N": Point(x=0, y=45.0),
            "S": Point(x=0, y=-45.0),
            "E": Point(x=45.0, y=0),
            "W": Point(x=-45.0, y=0)
        },
        runways=[],
        stars={}
    )
    save_airport_config(config)
    return config

def list_all_airports() -> List[AirportConfig]:
    airports = []
    for f in AIRPORTS_DIR.glob("*.json"):
        with open(f, "r") as json_file:
            data = json.load(json_file)
            airports.append(AirportConfig(**data))
    return airports

def geo_to_xy(lat: float, lon: float, anchor: LatLon) -> Point:
    # Planar projection logic: 111.32 km per degree lat
    # Center of 50x50km is (25, 25)
    KM_PER_DEG_LAT = 111.32
    # Y increases upwards in backend
    dy = (lat - anchor.lat) * KM_PER_DEG_LAT
    dx = (lon - anchor.lon) * (KM_PER_DEG_LAT * math.cos(math.radians(anchor.lat)))
    
    return Point(x=dx, y=dy)

def xy_to_latLon_list(x: float, y: float, anchor: LatLon) -> list:
    KM_PER_DEG_LAT = 111.32
    dx = x
    dy = y
    lat = anchor.lat + (dy / KM_PER_DEG_LAT)
    lon = anchor.lon + (dx / (KM_PER_DEG_LAT * math.cos(math.radians(anchor.lat))))
    return [round(lat, 6), round(lon, 6)]

def _add_approach_fixes(config: AirportConfig, rw_id: str, threshold: Point, heading: float) -> Point:
    """Internal helper to project FAF (9km) and IAF (20km) along extended centerline"""
    rad = math.radians(heading)
    # Unit vector in direction of landing (HEADING 0 is North +Y, 90 is East +X)
    dx = math.sin(rad)
    dy = math.cos(rad)
    
    # 1. Final Approach Fix (FAF) - 9km
    faf_p = Point(x=threshold.x - dx * 9.0, y=threshold.y - dy * 9.0)
    faf_id = f"FAF_{rw_id}"
    config.waypoints[faf_id] = WaypointConfig(
        id=faf_id, name=faf_id, x=faf_p.x, y=faf_p.y,
        target_alt=2000, target_speed=180, is_iaf=False, is_faf=True
    )
    
    # 2. Initial Approach Fix (IAF) - 20km
    iaf_p = Point(x=threshold.x - dx * 20.0, y=threshold.y - dy * 20.0)
    iaf_id = f"IAF_{rw_id}"
    config.waypoints[iaf_id] = WaypointConfig(
        id=iaf_id, name=iaf_id, x=iaf_p.x, y=iaf_p.y,
        target_alt=4000, target_speed=210, is_iaf=True
    )
    return iaf_p

def add_runway_from_geo(airport_code: str, start_latlon: list, end_latlon: list, bidirectional: bool = False) -> AirportConfig:
    # Find airport by code
    config = load_airport_config(airport_code)
    if not config:
        raise ValueError(f"Airport with code '{airport_code}' not found")
        
    p1 = geo_to_xy(start_latlon[0], start_latlon[1], config.anchor)
    p2 = geo_to_xy(end_latlon[0], end_latlon[1], config.anchor)
    
    # Calculate heading and length from XY
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    length = math.sqrt(dx**2 + dy**2)
    # Aviation: 0 North (+Y), 90 East (+X)
    heading = (90 - math.degrees(math.atan2(dy, dx))) % 360
    
    rw_id = f"RWY_{len(config.runways) + 1}"
    # Automatically project FAF/IAF
    iaf_point = _add_approach_fixes(config, rw_id, p1, heading)
    
    new_runway = RunwayConfig(
        id=rw_id,
        heading=heading,
        length_km=length,
        start=p1,
        end=p2,
        iaf=iaf_point
    )
    
    config.runways.append(new_runway)
    
    if bidirectional:
        # Create reverse runway (180 deg opposite)
        rev_id = f"{rw_id}_REV"
        rev_heading = (heading + 180) % 360
        # Automatically project FAF/IAF for the reverse side (start of reverse is p2)
        rev_iaf_point = _add_approach_fixes(config, rev_id, p2, rev_heading)
        
        config.runways.append(RunwayConfig(
            id=rev_id,
            heading=rev_heading,
            length_km=length,
            start=p2,
            end=p1,
            iaf=rev_iaf_point
        ))
        
    save_airport_config(config)
    return config

def add_runway(req: RunwayCreateRequest) -> AirportConfig:
    # Existing method for REST API
    config = load_airport_config(req.airport_code)
    if not config:
        raise ValueError(f"Airport {req.airport_code} not found")
        
    # Math for runway endpoints (heading 0=N, 90=E)
    rad = math.radians(req.heading)
    dx = math.sin(rad)
    dy = math.cos(rad)
    
    cx, cy = config.center.x, config.center.y
    half_len = req.length_km / 2.0
    
    start_p = Point(x=cx - dx * half_len, y=cy - dy * half_len)
    end_p = Point(x=cx + dx * half_len, y=cy + dy * half_len)
    
    # Automatically project FAF/IAF
    iaf_p = _add_approach_fixes(config, req.runway_id, start_p, req.heading)
    
    new_runway = RunwayConfig(
        id=req.runway_id,
        heading=req.heading,
        length_km=req.length_km,
        start=start_p,
        end=end_p,
        iaf=iaf_p
    )
    
    # Check if runway exists and replace or append
    config.runways = [rw for rw in config.runways if rw.id != req.runway_id]
    config.runways.append(new_runway)
    
    save_airport_config(config)
    return config

def add_waypoint(req: WaypointCreateRequest) -> AirportConfig:
    config = load_airport_config(req.airport_code)
    if not config:
        raise ValueError(f"Airport {req.airport_code} not found")
        
    wp = WaypointConfig(
        name=req.name or f"WP_{len(config.waypoints) + 1}",
        x=req.x,
        y=req.y,
        target_alt=req.target_alt or 3000,
        target_speed=req.target_speed or 210,
        is_iaf=req.is_iaf
    )
    
    config.waypoints[wp.id] = wp
    save_airport_config(config)
    return config

def save_star_route(req: StarRouteSaveRequest) -> AirportConfig:
    config = load_airport_config(req.airport_code)
    if not config:
        raise ValueError(f"Airport {req.airport_code} not found")
        
    if req.gate_id not in config.stars:
        config.stars[req.gate_id] = {}
        
    config.stars[req.gate_id][req.runway_id] = req.route_sequence
    save_airport_config(config)
    return config

def update_waypoint(req: WaypointUpdateRequest) -> AirportConfig:
    config = load_airport_config(req.airport_code)
    if not config:
        raise ValueError(f"Airport {req.airport_code} not found")
        
    # Pool architecture: lookup by waypoint_id
    if req.waypoint_id in config.waypoints:
        wp = config.waypoints[req.waypoint_id]
        if req.name is not None: wp.name = req.name
        if req.target_alt is not None: wp.target_alt = req.target_alt
        if req.target_speed is not None: wp.target_speed = req.target_speed
    else:
        # Fallback: find by name if ID lookup fails (old waypoints)
        for wp in config.waypoints.values():
            if wp.name == req.name:
                if req.target_alt is not None: wp.target_alt = req.target_alt
                if req.target_speed is not None: wp.target_speed = req.target_speed
                break
            
    save_airport_config(config)
    return config

def update_runway(req: RunwayUpdateRequest) -> AirportConfig:
    config = load_airport_config(req.airport_code)
    if not config:
        raise ValueError(f"Airport {req.airport_code} not found")
        
    for rw in config.runways:
        if rw.id == req.runway_id:
            if req.new_id: rw.id = req.new_id
            if req.heading is not None: rw.heading = req.heading
            break
            
    save_airport_config(config)
    return config

def delete_waypoint(airport_code: str, waypoint_id: str) -> Optional[AirportConfig]:
    config = load_airport_config(airport_code)
    if not config:
        return None
        
    # Remove from global pool
    if waypoint_id in config.waypoints:
        del config.waypoints[waypoint_id]
        
    # Cascade: remove ID from all star procedures
    for gate in config.stars:
        for rwy in config.stars[gate]:
            config.stars[gate][rwy] = [wp_id for wp_id in config.stars[gate][rwy] if wp_id != waypoint_id]
            
    save_airport_config(config)
    return config
def delete_runway(airport_code: str, runway_id: str) -> Optional[AirportConfig]:
    config = load_airport_config(airport_code)
    if not config:
        return None
        
    # Remove the runway and its reverse if applicable
    config.runways = [rw for rw in config.runways if rw.id != runway_id and rw.id != f"{runway_id}_REV"]
    
    # Cascade delete from stars (terminal procedures)
    for gate in config.stars:
        # pop() with None default avoids KeyError if the runway wasn't defined for a specific gate
        config.stars[gate].pop(runway_id, None)
        config.stars[gate].pop(f"{runway_id}_REV", None)
    
    save_airport_config(config)
    return config
