import subprocess
import os
import sys
import time


def kill_port_8000():
    try:
        if os.name == "nt":  # Windows
            # Find PID on port 8000
            result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
            for line in result.stdout.splitlines():
                if ":8000" in line and "LISTENING" in line:
                    parts = line.split()
                    pid = parts[-1]
                    print(f"Killing process {pid} on port 8000...")
                    subprocess.run(["taskkill", "/F", "/PID", pid], check=False)
                    time.sleep(1)
        else:  # Linux/Mac
            # Use lsof on macOS, fuser on Linux
            import platform

            system = platform.system()
            if system == "Darwin":  # macOS
                result = subprocess.run(
                    ["lsof", "-ti", "tcp:8000"], capture_output=True, text=True
                )
                pids = result.stdout.strip().split("\n")
                for pid in pids:
                    if pid:
                        print(f"Killing process {pid} on port 8000...")
                        subprocess.run(["kill", "-9", pid], check=False)
            else:  # Linux
                subprocess.run(["fuser", "-k", "8000/tcp"], check=False)
    except Exception as e:
        print(f"Error killing port: {e}")


import argparse


def run_server():
    parser = argparse.ArgumentParser(description="Run the ATC Simulation Server")
    parser.add_argument(
        "--ui", "-u", action="store_true", help="Start the backend and the frontend UI"
    )
    parser.add_argument(
        "--only-ui", action="store_true", help="Start ONLY the frontend UI (visualizer)"
    )
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)
    ui_dir = os.path.join(script_dir, "visualizer")

    # Helper to run pnpm commands robustly
    pnpm_exe = "pnpm.cmd" if os.name == "nt" else "pnpm"

    if args.only_ui:
        print("Starting ONLY Frontend (Vite)...")
        try:
            subprocess.run([pnpm_exe, "run", "dev"], cwd=ui_dir)
        except KeyboardInterrupt:
            print("\nStopping UI...")
        return

    kill_port_8000()

    # Start UI if flag provided
    ui_process = None
    if args.ui:
        print("Starting Frontend (Vite)...")
        try:
            ui_process = subprocess.Popen([pnpm_exe, "run", "dev"], cwd=ui_dir)
            print(f"Frontend process started (PID: {ui_process.pid})")
        except Exception as e:
            print(f"Error starting frontend: {e}")

    print("Starting backend...")
    env = os.environ.copy()
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = parent_dir + os.pathsep + env["PYTHONPATH"]
    else:
        env["PYTHONPATH"] = parent_dir

    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "atc_rl_api.api.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
            ],
            env=env,
        )
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        if ui_process:
            print("Terminating frontend process...")
            ui_process.terminate()
            ui_process.wait()


if __name__ == "__main__":
    run_server()
