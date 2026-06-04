import cv2
import numpy as np
import os
import json
import time
from datetime import datetime, timedelta
from ultralytics import YOLO
from backend.database import add_event, update_live_metrics

class CCTVProcessor:
    def __init__(self, video_path: str, camera_id: str, crowd_threshold: int = 4, loitering_threshold_sec: float = 15.0):
        self.video_path = video_path
        self.camera_id = camera_id
        self.crowd_threshold = crowd_threshold
        self.loitering_threshold_sec = loitering_threshold_sec
        
        # Load pre-trained YOLOv8n model (automatically downloads if not present)
        # In Docker, this is cached during build
        self.model = YOLO("yolov8n.pt")
        
        # Tracking state
        self.active_tracks = {}      # track_id -> first_seen_timestamp (video time)
        self.track_last_seen = {}    # track_id -> last_seen_frame_idx
        self.loitering_alerts_triggered = set()  # set of track_ids
        self.crowd_alert_active = False
        self.total_visitors_logged = set()  # set of track_ids
        
    def process_video_generator(self, frame_skip: int = 3, max_duration_sec: float = 60.0):
        """
        Generator function that processes the video frame by frame.
        Yields: (annotated_frame_bytes, current_people_count, list_of_new_events)
        """
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            print(f"Error: Could not open video file {self.video_path}")
            return
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0  # fallback
            
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_idx = 0
        
        # We simulate the actual event timestamp starting from 'now'
        start_time = datetime.now()
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            frame_idx += 1
            
            # Skip frames to speed up processing
            if frame_idx % frame_skip != 0:
                continue
                
            # Stop if we exceed max duration
            video_time_sec = frame_idx / fps
            if video_time_sec > max_duration_sec:
                break
                
            # Current simulated timestamp
            current_timestamp = (start_time + timedelta_helper(video_time_sec)).isoformat()
            
            # Run YOLOv8 tracking on the frame (only track 'person' class which is index 0)
            results = self.model.track(frame, persist=True, classes=[0], verbose=False)
            
            new_events = []
            current_people_count = 0
            
            # Process results
            annotated_frame = frame.copy()
            if results and len(results) > 0 and results[0].boxes is not None:
                boxes = results[0].boxes
                current_people_count = len(boxes)
                
                # Check for track IDs
                track_ids = boxes.id
                xyxys = boxes.xyxy.cpu().numpy()
                
                # Draw boxes and track IDs
                for idx, box in enumerate(xyxys):
                    # Bounding box coordinates
                    x1, y1, x2, y2 = map(int, box[:4])
                    
                    # Track ID
                    track_id = int(track_ids[idx].item()) if track_ids is not None else None
                    
                    # If we have a valid track ID
                    if track_id is not None:
                        # 1. PERSON_ENTERED event
                        if track_id not in self.active_tracks:
                            self.active_tracks[track_id] = video_time_sec
                            self.total_visitors_logged.add(track_id)
                            
                            event_details = {"person_id": track_id, "camera_id": self.camera_id}
                            add_event("PERSON_ENTERED", self.camera_id, track_id, event_details, current_timestamp)
                            new_events.append({
                                "event_type": "PERSON_ENTERED",
                                "timestamp": current_timestamp,
                                "camera_id": self.camera_id,
                                "person_id": track_id,
                                "details": event_details
                            })
                            
                        self.track_last_seen[track_id] = frame_idx
                        
                        # 2. LOITERING_ALERT event
                        dwell_time = video_time_sec - self.active_tracks[track_id]
                        if dwell_time >= self.loitering_threshold_sec and track_id not in self.loitering_alerts_triggered:
                            self.loitering_alerts_triggered.add(track_id)
                            
                            event_details = {
                                "person_id": track_id,
                                "camera_id": self.camera_id,
                                "duration_seconds": round(dwell_time, 1)
                            }
                            add_event("LOITERING_ALERT", self.camera_id, track_id, event_details, current_timestamp)
                            new_events.append({
                                "event_type": "LOITERING_ALERT",
                                "timestamp": current_timestamp,
                                "camera_id": self.camera_id,
                                "person_id": track_id,
                                "details": event_details
                            })
                            
                        # Draw label and bounding box
                        label = f"Person #{track_id}"
                        color = (0, 255, 0) # Green for active tracking
                        
                        # Highlight loiterers
                        if track_id in self.loitering_alerts_triggered:
                            color = (0, 0, 255) # Red for loitering alert
                            label += " (Loitering!)"
                            
                        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
                        cv2.putText(annotated_frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                    else:
                        # Draw generic person box if tracking id is not resolved yet
                        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (255, 255, 0), 2)
                        cv2.putText(annotated_frame, "Person", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
            
            # 3. CROWD_ALERT event
            if current_people_count >= self.crowd_threshold:
                if not self.crowd_alert_active:
                    self.crowd_alert_active = True
                    event_details = {
                        "count": current_people_count,
                        "threshold": self.crowd_threshold,
                        "message": f"Crowd detected! {current_people_count} people in view."
                    }
                    add_event("CROWD_ALERT", self.camera_id, None, event_details, current_timestamp)
                    new_events.append({
                        "event_type": "CROWD_ALERT",
                        "timestamp": current_timestamp,
                        "camera_id": self.camera_id,
                        "person_id": None,
                        "details": event_details
                    })
            else:
                self.crowd_alert_active = False
                
            # 4. PERSON_EXITED event (check for lost tracks)
            # A track is lost if it hasn't been seen in the last 10 processed steps (approx 1-2 seconds of video time)
            lost_tracks = []
            for track_id, last_seen_frame in self.track_last_seen.items():
                if track_id in self.active_tracks and (frame_idx - last_seen_frame) > (frame_skip * 10):
                    lost_tracks.append(track_id)
                    
            for track_id in lost_tracks:
                # Log exit
                event_details = {"person_id": track_id, "camera_id": self.camera_id}
                add_event("PERSON_EXITED", self.camera_id, track_id, event_details, current_timestamp)
                new_events.append({
                    "event_type": "PERSON_EXITED",
                    "timestamp": current_timestamp,
                    "camera_id": self.camera_id,
                    "person_id": track_id,
                    "details": event_details
                })
                
                # Cleanup tracking state
                self.active_tracks.pop(track_id, None)
                self.track_last_seen.pop(track_id, None)
                self.loitering_alerts_triggered.discard(track_id)
                
            # Update live metrics in DB
            crowd_alert_val = 1 if self.crowd_alert_active else 0
            update_live_metrics(self.camera_id, current_people_count, crowd_alert_val)
            
            # Overlay dashboard on the frame
            cv2.rectangle(annotated_frame, (10, 10), (250, 90), (0, 0, 0), -1)
            cv2.putText(annotated_frame, f"CAM: {self.camera_id}", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(annotated_frame, f"Count: {current_people_count}", (20, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            if self.crowd_alert_active:
                cv2.putText(annotated_frame, "CROWD ALERT", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            else:
                cv2.putText(annotated_frame, "Status: Normal", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
            # Encode frame to jpeg for web streaming
            _, buffer = cv2.imencode('.jpg', annotated_frame)
            frame_bytes = buffer.tobytes()
            
            yield frame_bytes, current_people_count, new_events
            
        # Clean up remaining active tracks at the end of the video
        end_timestamp = (start_time + timedelta_helper(video_time_sec if 'video_time_sec' in locals() else 0)).isoformat()
        for track_id in list(self.active_tracks.keys()):
            event_details = {"person_id": track_id, "camera_id": self.camera_id}
            add_event("PERSON_EXITED", self.camera_id, track_id, event_details, end_timestamp)
            
        cap.release()

def timedelta_helper(seconds: float):
    return timedelta(seconds=seconds)
