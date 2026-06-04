from fastapi import FastAPI, BackgroundTasks, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict, Any
import os
import glob
from backend.database import (
    seed_data_from_datasets,
    get_live_metrics,
    get_events,
    get_anomalies,
    get_store_summary,
    get_db_connection,
    init_db
)
from backend.processor import CCTVProcessor

app = FastAPI(
    title="CCTV Store Intelligence System API",
    description="Backend services for tracking person entries, exits, loitering, and crowd alerts.",
    version="1.0.0"
)

# Enable CORS for frontend integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Background processing state
active_background_tasks = {}

@app.on_event("startup")
def startup_event():
    # Automatically initialize and seed database on startup
    seed_data_from_datasets()

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "CCTV Store Intelligence System Backend",
        "docs_url": "/docs"
    }

@app.get("/metrics/live")
def get_live_metrics_endpoint():
    """Retrieve current occupancy and active alerts for all cameras."""
    try:
        metrics = get_live_metrics()
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/events")
def get_events_endpoint(
    event_type: Optional[str] = Query(None, description="Filter by event type (e.g. PERSON_ENTERED, PERSON_EXITED, CROWD_ALERT, LOITERING_ALERT)"),
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    limit: int = Query(100, ge=1, le=1000, description="Number of events to return")
):
    """Retrieve event logs with optional filtering by type and camera."""
    try:
        events = get_events(event_type=event_type, camera_id=camera_id, limit=limit)
        return events
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/anomalies")
def get_anomalies_endpoint(
    limit: int = Query(100, ge=1, le=1000, description="Number of anomalies to return")
):
    """Retrieve anomaly events (CROWD_ALERT and LOITERING_ALERT)."""
    try:
        anomalies = get_anomalies(limit=limit)
        return anomalies
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/store/summary")
def get_store_summary_endpoint():
    """Retrieve store-wide analytical summary (footfalls, conversion rate, busy hours, etc.)."""
    try:
        summary = get_store_summary()
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Additional endpoints to manage video processing
@app.get("/store/videos")
def list_available_videos():
    """List all extracted videos that are ready for processing."""
    extracted_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "extracted")
    
    video_files = []
    # Search recursively for mp4 files
    for filepath in glob.glob(os.path.join(extracted_dir, "**", "*.mp4"), recursive=True):
        rel_path = os.path.relpath(filepath, extracted_dir)
        video_files.append({
            "name": os.path.basename(filepath),
            "relative_path": rel_path.replace("\\", "/"),
            "absolute_path": filepath.replace("\\", "/")
        })
        
    return video_files

def run_video_processing_task(video_path: str, camera_id: str, crowd_threshold: int, loitering_threshold: float):
    processor = CCTVProcessor(
        video_path=video_path,
        camera_id=camera_id,
        crowd_threshold=crowd_threshold,
        loitering_threshold_sec=loitering_threshold
    )
    # Process up to 10 minutes of video, skipping 3 frames between tracks to speed it up
    try:
        active_background_tasks[camera_id] = "Processing"
        for _ in processor.process_video_generator(frame_skip=3, max_duration_sec=600.0):
            pass
        active_background_tasks[camera_id] = "Completed"
    except Exception as e:
        active_background_tasks[camera_id] = f"Failed: {str(e)}"

@app.post("/process/start")
def start_processing(
    video_relative_path: str,
    camera_id: str,
    background_tasks: BackgroundTasks,
    crowd_threshold: int = Query(4, description="People threshold for crowd alert"),
    loitering_threshold: float = Query(15.0, description="Dwell time threshold in seconds for loitering alert")
):
    """Start background YOLOv8 analysis on an extracted video file."""
    extracted_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "extracted")
    video_path = os.path.join(extracted_dir, video_relative_path)
    
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail=f"Video file not found at {video_relative_path}")
        
    if camera_id in active_background_tasks and active_background_tasks[camera_id] == "Processing":
        return {"status": "already_running", "camera_id": camera_id}
        
    background_tasks.add_task(
        run_video_processing_task,
        video_path,
        camera_id,
        crowd_threshold,
        loitering_threshold
    )
    
    return {
        "status": "started",
        "video": video_relative_path,
        "camera_id": camera_id
    }

@app.get("/process/status")
def get_processing_status():
    """Retrieve status of background video processing tasks."""
    return active_background_tasks

@app.post("/database/reset")
def reset_database():
    """Clear all database tables and seed with the sample datasets again."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS events")
        cursor.execute("DROP TABLE IF EXISTS live_metrics")
        cursor.execute("DROP TABLE IF EXISTS pos_transactions")
        conn.commit()
        conn.close()
        
        # Re-initialize and seed
        seed_data_from_datasets()
        return {"status": "success", "message": "Database reset and re-seeded successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
