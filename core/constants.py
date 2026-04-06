# Aircraft and Simulation Constants

# Airspace Radius (50km diameter = 25km radius)
AIRSPACE_RADIUS = 25.0

# Arrival Gates (Coordinates in km relative to airport at 0,0)
# N: +Y, S: -Y, E: +X, W: -X
ARRIVAL_GATES = {
    "NORTH": (0, 25),
    "SOUTH": (0, -25),
    "EAST": (25, 0),
    "WEST": (-25, 0)
}

# Runway Position (Anchor point is 0, 0)
RUNWAY_POS = (0, 0)
RUNWAY_HEADINGS = {
    "09": 90.0,
    "27": 270.0
}

# Initial Approach Fixes (IAFs) for both directions (relative to 0,0)
IAF_09_POS = (-20, 0) 
IAF_27_POS = (20, 0) 

# Holding Fixes (Standard orbits relative to 0,0)
HOLDING_FIXES = {
    "NORTH": (0, 10),
    "SOUTH": (0, -10),
    "EAST": (10, 0),
    "WEST": (-10, 0)
}

# Safety Separation
MIN_SEPARATION_DISTANCE = 5.0  # km
MIN_VERTICAL_SEPARATION = 1000  # ft
