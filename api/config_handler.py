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
    # 50x50km setup
    width = 50.0
    height = 50.0
    center_x = width / 2.0
    center_y = height / 2.0
    
    config = AirportConfig(
        airport_code=req.airport_code.upper(),
        name=req.name,
        anchor=LatLon(lat=req.anchor_lat, lon=req.anchor_lon),
        bounds={"width_km": 50.0, "height_km": 50.0},
        center=Point(x=0, y=0),
        gates={
            "N": Point(x=0, y=25.0),
            "S": Point(x=0, y=-25.0),
            "E": Point(x=25.0, y=0),
            "W": Point(x=-25.0, y=0)
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
    
    def generate_iaf(start, way_dx, way_dy):
        # 8-10km before threshold
        iaf_dist = random.uniform(8.0, 10.0)
        # Heading is from Start TO End. IAF is behind Start.
        # Normalize vector
        d_len = math.sqrt(way_dx**2 + way_dy**2)
        norm_dx = way_dx / d_len
        norm_dy = way_dy / d_len
        return Point(x=start.x - norm_dx * iaf_dist, y=start.y - norm_dy * iaf_dist)

    rw_id = f"RWY_{len(config.runways) + 1}"
    iaf_point = generate_iaf(p1, dx, dy)
    
    iaf_id = f"IAF-{rw_id}"
    iaf_wp = WaypointConfig(
        id=iaf_id,
        name=iaf_id,
        x=iaf_point.x,
        y=iaf_point.y,
        target_alt=3000,
        target_speed=210,
        is_iaf=True
    )
    
    new_runway = RunwayConfig(
        id=rw_id,
        heading=heading,
        length_km=length,
        start=p1,
        end=p2,
        iaf=iaf_point
    )
    
    config.runways.append(new_runway)
    # Add IAF to pool, but NOT to routes (per user instructions)
    config.waypoints[iaf_id] = iaf_wp
    
    if bidirectional:
        # Create reverse runway (180 deg opposite)
        rev_id = f"{rw_id}_REV"
        rev_heading = (heading + 180) % 360
        rev_iaf_point = generate_iaf(p2, -dx, -dy)
        rev_iaf_id = f"IAF-{rev_id}"
        rev_iaf_wp = WaypointConfig(
            id=rev_iaf_id,
            name=rev_iaf_id,
            x=rev_iaf_point.x,
            y=rev_iaf_point.y,
            target_alt=3000,
            target_speed=210,
            is_iaf=True
        )
        
        config.runways.append(RunwayConfig(
            id=rev_id,
            heading=rev_heading,
            length_km=length,
            start=p2,
            end=p1,
            iaf=rev_iaf_point
        ))
        # Add reverse IAF to pool
        config.waypoints[rev_iaf_id] = rev_iaf_wp
        
    save_airport_config(config)
    return config

def add_runway(req: RunwayCreateRequest) -> AirportConfig:
    # Existing method for REST API
    config = load_airport_config(req.airport_code)
    if not config:
        raise ValueError(f"Airport {req.airport_code} not found")
        
    # Math for runway endpoints
    # Aviation heading 0 is North (+Y), 90 is East (+X)
    rad = math.radians(req.heading)
    dx = math.sin(rad)
    dy = math.cos(rad)
    
    cx, cy = config.center.x, config.center.y
    half_len = req.length_km / 2.0
    
    start_p = Point(x=cx - dx * half_len, y=cy - dy * half_len)
    end_p = Point(x=cx + dx * half_len, y=cy + dy * half_len)
    
    # IAF: 8-10km before threshold
    iaf_dist = random.uniform(8.0, 10.0)
    iaf_p = Point(x=start_p.x - dx * iaf_dist, y=start_p.y - dy * iaf_dist)
    
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
        
    # In pool architecture, we look it up from the global pool either by sequence in a route or ID
    # But usually, it's better to update by ID directly. 
    # For now, let's look for any waypoint in the pool that might match (or we should update by ID)
    # Refactoring WaypointUpdateRequest to include ID would be better.
    # Let's assume for now we look in config.waypoints
    
    for wp in config.waypoints.values():
        if wp.id == req.gate_id: # Reusing existing field temporarily or assuming gate_id was used as ID
            if req.name is not None: wp.name = req.name
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
