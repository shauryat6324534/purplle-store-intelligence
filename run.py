import os
import zipfile
import subprocess
import sys
import time

def extract_data_if_needed():
    data_dir = "data"
    extracted_dir = os.path.join(data_dir, "extracted")
    
    # Check if we already have the extracted folders
    store1_extracted = os.path.join(extracted_dir, "Store 1")
    store2_extracted = os.path.join(extracted_dir, "Store 2")
    
    if os.path.exists(store1_extracted) and os.path.exists(store2_extracted):
        print("Data already extracted.")
        return
        
    print("Data directory not fully extracted. Extracting files...")
    os.makedirs(extracted_dir, exist_ok=True)
    
    # Find zip files in data/
    zip_files = [f for f in os.listdir(data_dir) if f.endswith(".zip")]
    
    for zf in zip_files:
        zip_path = os.path.join(data_dir, zf)
        print(f"Extracting {zip_path} to {extracted_dir}...")
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extracted_dir)
            print(f"Successfully extracted {zf}")
        except Exception as e:
            print(f"Error extracting {zf}: {e}")

def run_services():
    print("Starting CCTV Store Intelligence System Services...")
    
    # 1. Start FastAPI backend process
    print("Launching FastAPI backend on http://localhost:8000 ...")
    backend_cmd = [
        sys.executable, "-m", "uvicorn", "backend.main:app", 
        "--host", "0.0.0.0", 
        "--port", "8000"
    ]
    
    # 2. Start Streamlit frontend process
    print("Launching Streamlit dashboard on http://localhost:8501 ...")
    frontend_cmd = [
        sys.executable, "-m", "streamlit", "run", "frontend/dashboard.py",
        "--server.port", "8501",
        "--server.address", "0.0.0.0"
    ]
    
    processes = []
    try:
        # Start backend
        backend_proc = subprocess.Popen(backend_cmd)
        processes.append(backend_proc)
        
        # Wait a short moment for backend to initialize database and spin up
        time.sleep(3)
        
        # Start frontend
        frontend_proc = subprocess.Popen(frontend_cmd)
        processes.append(frontend_proc)
        
        # Keep main thread alive and monitor processes
        print("Both services are running. Press Ctrl+C to terminate.")
        while True:
            for p in processes:
                if p.poll() is not None:
                    # One of the processes died
                    print(f"Process {p.args} exited with code {p.returncode}")
                    return
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping services...")
    finally:
        for p in processes:
            if p.poll() is None:
                print(f"Terminating process: {p.args[2] if len(p.args) > 2 else p.args}")
                p.terminate()
                try:
                    p.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    p.kill()

if __name__ == "__main__":
    # Ensure correct working directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Extract zip data
    extract_data_if_needed()
    
    # Run the services
    run_services()
