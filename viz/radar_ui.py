# Pygame radar rendering UI

import pygame
import requests
import sys

# Simulation API URL
API_URL = "http://localhost:8000"

def run_radar_ui():
    pygame.init()
    screen_size = 600
    screen = pygame.display.set_mode((screen_size, screen_size))
    pygame.display.set_caption("ATC Radar View")
    clock = pygame.time.Clock()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Request state from API
        try:
            response = requests.get(f"{API_URL}/state")
            state = response.json()
            
            # Step simulation from UI (just for demo)
            requests.post(f"{API_URL}/step")
        except Exception as e:
            print(f"Error connecting to API: {e}")
            state = {"time": 0, "aircrafts": []}

        # Render
        screen.fill((5, 20, 5))  # Dark green background
        
        # Draw grid
        for i in range(1, 6):
            pygame.draw.circle(screen, (30, 80, 30), (300, 300), i * 60, 1)

        # Draw aircrafts
        for ac in state["aircrafts"]:
            # Coordinate scaling (0-100km to 0-600px)
            px = int(ac["x"] * 6)
            py = int(ac["y"] * 6)
            
            pygame.draw.circle(screen, (255, 255, 255), (px, py), 5)
            # Display callsign
            font = pygame.font.SysFont("Arial", 12)
            label = font.render(f"{ac['callsign']} {ac['altitude']}", True, (0, 255, 0))
            screen.blit(label, (px + 10, py - 10))

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    run_radar_ui()
