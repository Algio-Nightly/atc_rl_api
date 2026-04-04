# Script to launch the FastAPI server

import uvicorn

def main():
    print("Launching ATC RL API server...")
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()
