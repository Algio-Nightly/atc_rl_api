import os
import json
from pathlib import Path

# Path to the airports directory
AIRPORTS_DIR = Path(__file__).parent.parent / "airports"

def clear_all_configs():
    print(f"Cleaning all airport configs in {AIRPORTS_DIR}...")
    if not AIRPORTS_DIR.exists():
        print("Error: airports directory not found.")
        return

    for json_file in AIRPORTS_DIR.glob("*.json"):
        print(f"Processing {json_file.name}...")
        try:
            with open(json_file, 'r') as f:
                config = json.load(f)
            
            # Clear waypoints and stars
            config['waypoints'] = {}
            config['stars'] = {}
            
            # Optional: Clear runways if you want to regenerate them from scratch in UI
            # config['runways'] = []
            
            with open(json_file, 'w') as f:
                json.dump(config, f, indent=2)
            print(f"Successfully cleared {json_file.name}")
        except Exception as e:
            print(f"Failed to process {json_file.name}: {e}")

if __name__ == "__main__":
    clear_all_configs()
