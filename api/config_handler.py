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
    WaypointConfig
)

AIRPORTS_DIR = Path("atc_rl_api/airports")
AIRPORTS_DIR.mkdir(exist_ok=True)

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
        bounds={"width_km": width, "height_km": height},
        center=Point(x=center_x, y=center_y),
        gates={
            "N": Point(x=center_x, y=height),
            "S": Point(x=center_x, y=0),
            "E": Point(x=width, y=center_y),
            "W": Point(x=0, y=center_y)
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
    
    return Point(x=25 + dx, y=25 + dy)

def xy_to_latLon_list(x: float, y: float, anchor: LatLon) -> list:
    KM_PER_DEG_LAT = 111.32
    dx = x - 25
    dy = y - 25
    lat = anchor.lat + (dy / KM_PER_DEG_LAT)
    lon = anchor.lon + (dx / (KM_PER_DEG_LAT * math.cos(math.radians(anchor.lat))))
    return [round(lat, 6), round(lon, 6)]

def add_runway_from_geo(airport_name: str, start_latlon: list, end_latlon: list, bidirectional: bool = False) -> AirportConfig:
    # Find airport by name
    all_ap = list_all_airports()
    config = next((a for a in all_ap if a.name == airport_name), None)
    if not config:
        raise ValueError(f"Airport with name '{airport_name}' not found")
        
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
    new_runway = RunwayConfig(
        id=rw_id,
        heading=heading,
        length_km=length,
        start=p1,
        end=p2,
        iaf=generate_iaf(p1, dx, dy)
    )
    
    config.runways.append(new_runway)
    
    if bidirectional:
        # Create reverse runway (180 deg opposite)
        rev_id = f"{rw_id}_REV"
        rev_heading = (heading + 180) % 360
        config.runways.append(RunwayConfig(
            id=rev_id,
            heading=rev_heading,
            length_km=length,
            start=p2,
            end=p1,
            iaf=generate_iaf(p2, -dx, -dy)
        ))
        
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
    
    # Initialize star structure if missing
    if req.gate_id not in config.stars:
        config.stars[req.gate_id] = {}
    if req.target_runway not in config.stars[req.gate_id]:
        config.stars[req.gate_id][req.target_runway] = []
        
    wp = WaypointConfig(x=req.x, y=req.y)
    
    route = config.stars[req.gate_id][req.target_runway]
    if req.sequence_index == -1 or req.sequence_index >= len(route):
        route.append(wp)
    else:
        route.insert(req.sequence_index, wp)
        
    save_airport_config(config)
    return config

def delete_waypoint(req: WaypointDeleteRequest) -> AirportConfig:
    config = load_airport_config(req.airport_code)
    if not config:
        raise ValueError(f"Airport {req.airport_code} not found")
        
    if (req.gate_id in config.stars and 
        req.target_runway in config.stars[req.gate_id] and
        0 <= req.sequence_index < len(config.stars[req.gate_id][req.target_runway])):
        
        config.stars[req.gate_id][req.target_runway].pop(req.sequence_index)
        save_airport_config(config)
        
    return config
def delete_runway(airport_name: str, runway_id: str) -> Optional[AirportConfig]:
    all_ap = list_all_airports()
    config = next((a for a in all_ap if a.name == airport_name), None)
    if not config:
        return None
        
    # Remove the runway and its reverse if applicable
    original_count = len(config.runways)
    config.runways = [rw for rw in config.runways if rw.id != runway_id and rw.id != f"{runway_id}_REV"]
    
    if len(config.runways) < original_count:
        save_airport_config(config)
        return config
    return None
