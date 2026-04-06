import subprocess
import os
import sys
import time

def kill_port_8000():
    try:
        if os.name == 'nt': # Windows
            # Find PID on port 8000
            result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
            for line in result.stdout.splitlines():
                if ':8000' in line and 'LISTENING' in line:
                    parts = line.split()
                    pid = parts[-1]
                    print(f"Killing process {pid} on port 8000...")
                    subprocess.run(['taskkill', '/F', '/PID', pid], check=False)
                    time.sleep(1)
        else: # Linux/Mac
            subprocess.run(['fuser', '-k', '8000/tcp'], check=False)
    except Exception as e:
        print(f"Error killing port: {e}")

def run_server():
    kill_port_8000()
    print("Starting server...")
    try:
        subprocess.run([sys.executable, "-m", "uvicorn", "atc_rl_api.api.main:app", "--host", "0.0.0.0", "--port", "8000"])
    except KeyboardInterrupt:
        print("Stopping server.")

if __name__ == "__main__":
    run_server()
