# Standard Terminal Arrival Routes (STARs) definitions
from .constants import IAF_09_POS, IAF_27_POS

# 3D Waypoint structure: (x, y, target_alt, target_speed)
# Coordinates in km, Altitude in feet, Speed in knots

IAF_09 = {"id": "IAF_09", "x": IAF_09_POS[0], "y": IAF_09_POS[1], "target_alt": 3000, "target_speed": 180}
IAF_27 = {"id": "IAF_27", "x": IAF_27_POS[0], "y": IAF_27_POS[1], "target_alt": 3000, "target_speed": 180}

STAR_MATRIX = {
    "09": {  # Landing towards East (facing 090)
        "NORTH": [
            {"id": "N1_09", "x": 10, "y": 10, "target_alt": 10000, "target_speed": 250},
            {"id": "N2_09", "x": 10, "y": 30, "target_alt": 5000, "target_speed": 210},
            IAF_09
        ],
        "SOUTH": [
            {"id": "S1_09", "x": 10, "y": 90, "target_alt": 10000, "target_speed": 250},
            {"id": "S2_09", "x": 10, "y": 70, "target_alt": 5000, "target_speed": 210},
            IAF_09
        ],
        "EAST": [
            {"id": "E1_09", "x": 80, "y": 20, "target_alt": 10000, "target_speed": 250},
            IAF_09
        ],
        "WEST": [
            {"id": "W1_09", "x": 5, "y": 50, "target_alt": 10000, "target_speed": 250},
            IAF_09
        ]
    },
    "27": {  # Landing towards West (facing 270)
        "NORTH": [
            {"id": "N1_27", "x": 90, "y": 10, "target_alt": 10000, "target_speed": 250},
            {"id": "N2_27", "x": 90, "y": 30, "target_alt": 5000, "target_speed": 210},
            IAF_27 
        ],
        "SOUTH": [
            {"id": "S1_27", "x": 90, "y": 90, "target_alt": 10000, "target_speed": 250},
            {"id": "S2_27", "x": 90, "y": 70, "target_alt": 5000, "target_speed": 210},
            IAF_27
        ],
        "EAST": [
            {"id": "E1_27", "x": 95, "y": 50, "target_alt": 10000, "target_speed": 250},
            IAF_27
        ],
        "WEST": [
            {"id": "W1_27", "x": 20, "y": 80, "target_alt": 10000, "target_speed": 250},
            IAF_27
        ]
    }
}
