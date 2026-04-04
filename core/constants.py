# Aircraft and Simulation Constants

# Arrival Gates (Coordinates in km)
ARRIVAL_GATES = {
    "NORTH": (50, 0),
    "SOUTH": (50, 100),
    "EAST": (100, 50),
    "WEST": (0, 50)
}

# Runway (Dual-ended strip)
RUNWAY_POS = (50, 50)
RUNWAY_HEADINGS = {
    "09": 90.0,  # Facing East (Land from West)
    "27": 270.0  # Facing West (Land from East)
}

# Initial Approach Fixes (IAFs) for both directions
IAF_09_POS = (10, 50) 
IAF_27_POS = (90, 50) 

# Holding Fixes (Standard orbits for traffic management)
HOLDING_FIXES = {
    "NORTH": (50, 20),
    "SOUTH": (50, 80),
    "EAST": (80, 50),
    "WEST": (20, 50)
}

# Safety Separation
MIN_SEPARATION_DISTANCE = 5.0  # km
MIN_VERTICAL_SEPARATION = 1000  # ft
