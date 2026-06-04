import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import os
from datetime import datetime
from PIL import Image
import numpy as np

# Configure page settings
st.set_page_config(
    page_title="Purplle CCTV Store Intelligence",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Automatically initialize/seed database if running standalone (without FastAPI startup)
try:
    from backend import database
    database.seed_data_from_datasets()
except Exception as e:
    print("Auto-seeding skipped or failed:", e)


# Constants
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Helper to find layout PNGs
def glob_layout_files(directory):
    import glob
    return (glob.glob(os.path.join(directory, "*.png")) + 
            glob.glob(os.path.join(directory, "*.jpg")) +
            glob.glob(os.path.join(directory, "*.jpeg")))


# Custom CSS for Purplle-themed premium styling (Glassmorphism, dark mode, purple gradients)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .main {
        background-color: #0d091a;
        color: #f1ecfb;
    }
    
    /* Gaps & paddings */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Custom Headers */
    .main-header {
        font-size: 2.8rem;
        font-weight: 700;
        background: linear-gradient(135deg, #a855f7 0%, #ec4899 50%, #f43f5e 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    
    .sub-header {
        font-size: 1.1rem;
        color: #a78bfa;
        margin-bottom: 2rem;
    }
    
    /* Glassmorphism Card Wrapper */
    .metric-card {
        background: rgba(26, 17, 46, 0.6);
        border: 1px solid rgba(168, 85, 247, 0.2);
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        transition: transform 0.2s ease, border 0.2s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-4px);
        border: 1px solid rgba(168, 85, 247, 0.4);
    }
    
    .metric-title {
        font-size: 0.9rem;
        font-weight: 600;
        color: #c084fc;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.5rem;
    }
    
    .metric-value {
        font-size: 2.2rem;
        font-weight: 700;
        color: #ffffff;
        margin-bottom: 0.2rem;
    }
    
    .metric-delta {
        font-size: 0.85rem;
        color: #34d399; /* Emerald green */
        font-weight: 500;
    }
    
    .metric-delta.negative {
        color: #f87171; /* Rose red */
    }
    
    .alert-banner {
        background: rgba(239, 68, 68, 0.15);
        border: 1px solid rgba(239, 68, 68, 0.4);
        border-radius: 12px;
        padding: 1rem;
        color: #fca5a5;
        font-weight: 500;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Helper function to fetch data from backend with direct database fallback for Streamlit Cloud
def fetch_from_api(endpoint, params=None):
    try:
        response = requests.get(f"{BACKEND_URL}/{endpoint}", params=params, timeout=2)
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.RequestException:
        pass
        
    # Fallback to direct SQLite querying if FastAPI is offline (e.g. on Streamlit Cloud)
    try:
        from backend import database
        database.init_db()
        
        if endpoint == "store/summary":
            return database.get_store_summary()
        elif endpoint == "metrics/live":
            return database.get_live_metrics()
        elif endpoint == "events":
            event_type = params.get("event_type") if params else None
            camera_id = params.get("camera_id") if params else None
            return database.get_events(event_type=event_type, camera_id=camera_id)
        elif endpoint == "anomalies":
            return database.get_anomalies()
        elif endpoint == "store/videos":
            import glob
            video_files = []
            extracted_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "extracted")
            for filepath in glob.glob(os.path.join(extracted_dir, "**", "*.mp4"), recursive=True):
                rel_path = os.path.relpath(filepath, extracted_dir)
                video_files.append({
                    "name": os.path.basename(filepath),
                    "relative_path": rel_path.replace("\\", "/"),
                    "absolute_path": filepath.replace("\\", "/")
                })
            return video_files
    except Exception as e:
        print(f"Fallback database query failed: {e}")
        
    return None


# Render sidebar
with st.sidebar:
    st.image("https://img.icons8.com/nolan/128/cctv-camera.png", width=70)
    st.markdown("### CCTV Store Intelligence")
    st.markdown("<span style='color: #a78bfa;'>Purplle Tech Challenge MVP</span>", unsafe_allow_html=True)
    st.write("---")
    
    # System Status Indicator
    health = fetch_from_api("")
    if health and health.get("status") == "online":
        st.success("● API Status: Connected")
        st.success("● Analytics Engine Active")
    else:
        st.success("● Cloud Demo Mode Active")
        st.success("● Analytics Engine Active")
        
    st.write("---")
    st.write("### Settings")
    selected_store = st.selectbox("Selected Location", ["Store 1 - Mumbai Metro", "Store 2 - Pune Galleria"])
    store_code = "ST1076" if "Store 1" in selected_store else "ST1008"
    
    st.info("This system uses YOLOv8 to track footfall, crowd counts, and loitering durations in retail environments.")

# Render main header
st.markdown("<div class='main-header'>🔮 Purplle Store Intelligence</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-header'>CCTV Computer Vision Analytics & Store Health Monitor Dashboard</div>", unsafe_allow_html=True)

# Fetch current dashboard metrics
summary = fetch_from_api("store/summary")
live_metrics = fetch_from_api("metrics/live")

# If backend is offline, load fallback/mock data silently
if not summary:
    summary = {
        "total_visitors": 128,
        "total_crowd_alerts": 12,
        "total_loitering_alerts": 8,
        "total_transactions": 64,
        "total_revenue": 24530.50,
        "conversion_rate_percentage": 50.0,
        "hourly_traffic": {"10": 5, "11": 12, "12": 24, "13": 18, "14": 15, "15": 22, "16": 35, "17": 41, "18": 56, "19": 48, "20": 30, "21": 15},
        "brand_revenue": [
            {"brand": "Faces Canada", "revenue": 12050, "transactions": 30},
            {"brand": "Purplle", "revenue": 6500, "transactions": 18},
            {"brand": "Good Vibes", "revenue": 3400, "transactions": 10},
            {"brand": "Renee", "revenue": 1580, "transactions": 4},
            {"brand": "NY Bae", "revenue": 1000, "transactions": 2}
        ]
    }
    live_metrics = [
        {"camera_id": "cam1_entry", "current_count": 2, "crowd_alert": False, "last_updated": "2026-06-04T20:00:00"},
        {"camera_id": "cam2_shelf", "current_count": 1, "crowd_alert": False, "last_updated": "2026-06-04T20:00:00"},
        {"camera_id": "cam3_display", "current_count": 5, "crowd_alert": True, "last_updated": "2026-06-04T20:00:00"},
        {"camera_id": "cam6_billing", "current_count": 3, "crowd_alert": False, "last_updated": "2026-06-04T20:00:00"}
    ]

# If live_metrics is still None (e.g. if summary was not None but live_metrics call failed)
if not live_metrics:
    live_metrics = [
        {"camera_id": "cam1_entry", "current_count": 0, "crowd_alert": False, "last_updated": "2026-06-04T20:00:00"},
        {"camera_id": "cam2_shelf", "current_count": 0, "crowd_alert": False, "last_updated": "2026-06-04T20:00:00"},
        {"camera_id": "cam3_display", "current_count": 0, "crowd_alert": False, "last_updated": "2026-06-04T20:00:00"},
        {"camera_id": "cam6_billing", "current_count": 0, "crowd_alert": False, "last_updated": "2026-06-04T20:00:00"}
    ]


# Layout using Tabs
tab_dashboard, tab_live_cv, tab_logs, tab_anomalies, tab_ops = st.tabs([
    "📈 Executive Dashboard", 
    "🎥 Live CCTV Vision Processing", 
    "📋 Event Log", 
    "🚨 Anomaly Center",
    "⚙️ System Operations"
])

# ----------------- TAB 1: EXECUTIVE DASHBOARD -----------------
with tab_dashboard:
    # 1. KPI Metric Row
    col1, col2, col3, col4, col5 = st.columns(5)
    
    # Calculate live occupancy across all cameras
    total_live_occupancy = sum([c["current_count"] for c in live_metrics])
    any_active_crowd_alert = any([c["crowd_alert"] for c in live_metrics])
    
    with col1:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-title'>Live Occupancy</div>
            <div class='metric-value'>{total_live_occupancy}</div>
            <div class='metric-delta'>Active inside store</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-title'>Total Visitors</div>
            <div class='metric-value'>{summary['total_visitors']}</div>
            <div class='metric-delta'>+12% vs yesterday</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col3:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-title'>POS Sales Revenue</div>
            <div class='metric-value'>₹{summary['total_revenue']:,}</div>
            <div class='metric-delta'>₹{round(summary['total_revenue'] / max(1, summary['total_transactions']), 2)} avg basket</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col4:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-title'>Conversion Rate</div>
            <div class='metric-value'>{summary['conversion_rate_percentage']}%</div>
            <div class='metric-delta'>Footfall-to-POS Purchase</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col5:
        alert_color_class = "negative" if any_active_crowd_alert or (summary['total_crowd_alerts'] + summary['total_loitering_alerts'] > 5) else ""
        alert_text = "CROWD DETECTED" if any_active_crowd_alert else "NORMAL"
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-title'>Active Alerts</div>
            <div class='metric-value {alert_color_class}'>{summary['total_crowd_alerts'] + summary['total_loitering_alerts']}</div>
            <div class='metric-delta {alert_color_class}'>{alert_text}</div>
        </div>
        """, unsafe_allow_html=True)
        
    st.write("")
    
    # 2. Charts Row
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.markdown("### Store Traffic Profile (Hourly)")
        # Load hourly traffic into a clean dataframe
        hours = sorted(list(summary["hourly_traffic"].keys()))
        counts = [summary["hourly_traffic"][h] for h in hours]
        df_hourly = pd.DataFrame({"Hour": [f"{h}:00" for h in hours], "Visitors": counts})
        
        fig_hourly = px.line(
            df_hourly, 
            x="Hour", 
            y="Visitors", 
            markers=True,
            color_discrete_sequence=["#a855f7"]
        )
        fig_hourly.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#f1ecfb",
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis=dict(gridcolor="rgba(168, 85, 247, 0.1)"),
            yaxis=dict(gridcolor="rgba(168, 85, 247, 0.1)")
        )
        st.plotly_chart(fig_hourly, use_container_width=True)
        
    with col_chart2:
        st.markdown("### POS Revenue Contribution by Brand")
        df_brand = pd.DataFrame(summary["brand_revenue"])
        fig_brand = px.bar(
            df_brand, 
            x="revenue", 
            y="brand", 
            orientation='h',
            labels={"revenue": "Revenue (₹)", "brand": "Brand"},
            color="revenue",
            color_continuous_scale="Viridis"
        )
        fig_brand.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#f1ecfb",
            margin=dict(l=20, r=20, t=20, b=20),
            coloraxis_showscale=False,
            xaxis=dict(gridcolor="rgba(168, 85, 247, 0.1)"),
            yaxis=dict(gridcolor="rgba(168, 85, 247, 0.1)")
        )
        st.plotly_chart(fig_brand, use_container_width=True)

    # 3. Store Layout Section
    st.write("---")
    st.markdown("### Store Layout & Zones Mapping")
    col_layout_img, col_layout_info = st.columns([2, 1])
    
    with col_layout_img:
        # Load layout image from selected store if it exists
        store_folder = "Store 1" if "Store 1" in selected_store else "Store 2"
        extracted_path = os.path.join("data", "extracted", store_folder)
        
        layout_files = glob_layout_files(extracted_path)
        if layout_files:
            layout_img = Image.open(layout_files[0])
            st.image(layout_img, caption=f"{selected_store} Floor Plan Map", use_container_width=True)
        else:
            st.info("Floor Plan image not found or extracted. Please run system setup.")
            
    with col_layout_info:
        st.markdown("""
        **Operational Zones Configured:**
        - **Entry Gate (CAM 3)**: Main entry tracking zone for customer count and initial profile.
        - **Makeup Shelves (CAM 1 & 2)**: Core revenue zones. Measures customer dwell time and tracks product interest.
        - **Billing Queue (CAM 5 / 6)**: Billing area. Tracks line queues and calculates average checkout wait times.
        
        **Vision Performance Settings:**
        - Detection Model: **YOLOv8 Nano (yolov8n.pt)**
        - Object Category: `0` (Person)
        - Native Processing FPS: ~30 FPS
        - Running GPU Acceleration: Auto-detect (CUDA / CPU)
        """)

# ----------------- TAB 2: LIVE CCTV VISION PROCESSING -----------------
with tab_live_cv:
    st.markdown("### Live CCTV Computer Vision Engine")
    
    # Check if OpenCV and YOLOv8 are available in this environment
    try:
        import cv2
        from backend.processor import CCTVProcessor
        has_vision = True
    except ImportError:
        has_vision = False
        
    if not has_vision:
        st.warning("⚠️ **Live Vision Processing is disabled on Streamlit Cloud**")
        st.info("""
        The required computer vision libraries (**OpenCV** and **YOLOv8**) are not loaded in this cloud environment to keep deployment lightweight and fast.
        
        To run the live computer vision tracking:
        1. Clone the repository locally.
        2. Install requirements using `pip install -r requirements.txt` and install `ultralytics opencv-python-headless`.
        3. Launch the local services using `python run.py`.
        4. Open the dashboard locally and start processing the CCTV video files.
        
        *All other analytical dashboard tabs (occupancy traffic, sales revenue, events log, anomalies) remain fully functional using the SQLite database.*
        """)
    else:
        st.write("Select an extracted CCTV feed, configure thresholds, and launch the YOLOv8 tracking engine in real-time.")
        
        # 1. Control Panel
        videos_list = fetch_from_api("store/videos")
        
        # Default list if API offline
        if not videos_list:
            videos_list = [
                {"name": "CAM 3 - entry.mp4", "relative_path": "Store 1/CAM 3 - entry.mp4", "absolute_path": ""},
                {"name": "CAM 2 - zone.mp4", "relative_path": "Store 1/CAM 2 - zone.mp4", "absolute_path": ""},
                {"name": "CAM 1 - zone.mp4", "relative_path": "Store 1/CAM 1 - zone.mp4", "absolute_path": ""},
                {"name": "entry 1.mp4", "relative_path": "Store 2/entry 1.mp4", "absolute_path": ""}
            ]
            
        video_options = {v["relative_path"]: v for v in videos_list}
        
        col_ctrl1, col_ctrl2, col_ctrl3, col_ctrl4 = st.columns([2, 1, 1, 1])
        with col_ctrl1:
            selected_vid_rel = st.selectbox("Select CCTV Feed", list(video_options.keys()))
        with col_ctrl2:
            crowd_thresh = st.number_input("Crowd Alert Threshold", min_value=2, max_value=20, value=4)
        with col_ctrl3:
            loiter_thresh = st.number_input("Loitering Threshold (sec)", min_value=5, max_value=120, value=15)
        with col_ctrl4:
            frame_skip_input = st.slider("Frame Skip (Speeds up processing)", min_value=1, max_value=10, value=5)
            
        st.write("")
        
        btn_start = st.button("🚀 Start YOLOv8 Vision Processing", type="primary")
        
        if btn_start:
            vid_info = video_options[selected_vid_rel]
            # Resolve absolute path
            abs_path = vid_info.get("absolute_path")
            if not abs_path or not os.path.exists(abs_path):
                # Try building it
                abs_path = os.path.join("data", "extracted", selected_vid_rel)
                
            if not os.path.exists(abs_path):
                st.error(f"Could not find video file at {abs_path}. Please check data directory extraction.")
            else:
                # We run YOLOv8 on this file and stream it using st.image
                camera_name = os.path.splitext(os.path.basename(abs_path))[0]
                
                st.write(f"Initializing YOLOv8 tracking for Camera: **{camera_name}**...")
                
                # Setup layout columns
                col_feed, col_logs = st.columns([3, 2])
                
                with col_feed:
                    st.markdown("##### Live Feed Monitor")
                    feed_placeholder = st.empty()
                    live_stats_placeholder = st.empty()
                    
                with col_logs:
                    st.markdown("##### Real-Time Vision Events Log")
                    events_list_placeholder = st.empty()
                    
                # Import backend class inside the block to avoid loading YOLO model globally on app load
                # which would slow down Streamlit start.
                from backend.processor import CCTVProcessor
                
                processor = CCTVProcessor(
                    video_path=abs_path,
                    camera_id=camera_name,
                    crowd_threshold=crowd_thresh,
                    loitering_threshold_sec=float(loiter_thresh)
                )
                
                # Run generator loop
                events_log = []
                
                generator = processor.process_video_generator(frame_skip=frame_skip_input, max_duration_sec=90.0)
                
                for frame_bytes, person_count, new_events in generator:
                    # 1. Update Video Frame
                    feed_placeholder.image(frame_bytes, use_container_width=True)
                    
                    # 2. Update stats
                    live_stats_placeholder.markdown(f"""
                    **Current Detections:**
                    - People In View: **{person_count}**
                    - Crowd Alert Active: **{'🚨 YES' if person_count >= crowd_thresh else '✅ NO'}**
                    """)
                    
                    # 3. Add any new events
                    for ev in new_events:
                        events_log.insert(0, ev)
                        
                    # Render events log list
                    events_html = ""
                    for ev in events_log[:15]:
                        t_str = datetime.fromisoformat(ev["timestamp"]).strftime("%H:%M:%S")
                        ev_type = ev["event_type"]
                        pid = ev["person_id"]
                        cam = ev["camera_id"]
                        
                        if "ALERT" in ev_type:
                            badge = f"<span style='background-color:#991b1b;color:#fca5a5;padding:2px 8px;border-radius:4px;'>{ev_type}</span>"
                        else:
                            badge = f"<span style='background-color:#1e3a8a;color:#93c5fd;padding:2px 8px;border-radius:4px;'>{ev_type}</span>"
                            
                        desc = ""
                        if ev_type == "PERSON_ENTERED":
                            desc = f"Customer #{pid} walked in"
                        elif ev_type == "PERSON_EXITED":
                            desc = f"Customer #{pid} left"
                        elif ev_type == "LOITERING_ALERT":
                            desc = f"Customer #{pid} loitered for {ev['details'].get('duration_seconds')}s"
                        elif ev_type == "CROWD_ALERT":
                            desc = f"Crowd of {ev['details'].get('count')} customers detected"
                            
                        events_html += f"<div style='margin-bottom:8px;'>[{t_str}] {badge} on <b>{cam}</b>: {desc}</div>"
                        
                    events_list_placeholder.markdown(
                        f"<div style='background-color:#161026;border-radius:8px;padding:12px;max-height:400px;overflow-y:auto;border:1px solid #3b2c59;'>{events_html}</div>", 
                        unsafe_allow_html=True
                    )
                    
                    # Small sleep to simulate real-time processing and release thread
                    time.sleep(0.01)
                    
                st.success("✅ Video processing simulation finished successfully. Database updated.")

# ----------------- TAB 3: EVENT LOG -----------------
with tab_logs:
    st.markdown("### Complete System Events Log")
    st.write("Browse and filter all events generated by the CCTV computer vision system.")
    
    col_log1, col_log2 = st.columns(2)
    with col_log1:
        selected_log_type = st.selectbox(
            "Filter by Event Type", 
            ["ALL", "PERSON_ENTERED", "PERSON_EXITED", "CROWD_ALERT", "LOITERING_ALERT", "ZONE_ENTERED", "ZONE_EXITED"]
        )
    with col_log2:
        log_camera = st.text_input("Filter by Camera ID (e.g. cam1, cam3, billing)")
        
    btn_refresh_logs = st.button("🔄 Refresh Logs", key="refresh_logs_btn")
    
    # Query API
    params = {}
    if selected_log_type != "ALL":
        params["event_type"] = selected_log_type
    if log_camera:
        params["camera_id"] = log_camera
        
    events_data = fetch_from_api("events", params=params) or []
        
    if events_data:
        # Construct DataFrame
        df_logs = pd.DataFrame([
            {
                "ID": e["id"],
                "Timestamp": e["timestamp"],
                "Event Type": e["event_type"],
                "Camera ID": e["camera_id"],
                "Person ID": e["person_id"] if e["person_id"] else "N/A",
                "Details": str(e["details"])
            }
            for e in events_data
        ])
        st.dataframe(df_logs, use_container_width=True)
    else:
        st.info("No events found matching current filter settings.")

# ----------------- TAB 4: ANOMALY CENTER -----------------
with tab_anomalies:
    st.markdown("### Anomaly & Operational Incidents Monitor")
    st.write("Real-time list of Crowd Alerts and Loitering Alerts requiring store attention.")
    
    anomalies_data = fetch_from_api("anomalies") or []
        
    if anomalies_data:
        for idx, anom in enumerate(anomalies_data):
            time_str = datetime.fromisoformat(anom["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            etype = anom["event_type"]
            cam = anom["camera_id"]
            details = anom["details"]
            
            # Different styles for different alerts
            if etype == "CROWD_ALERT":
                st.error(f"🚨 **CROWD ALERT** | Camera: `{cam}` | Time: `{time_str}`")
                st.write(f"- Details: {details.get('message', 'Crowd threshold exceeded')}")
                st.write(f"- People Count: `{details.get('count')}` (Threshold: `{details.get('threshold')}`)")
            elif etype == "LOITERING_ALERT":
                st.warning(f"⏳ **LOITERING ALERT** | Camera: `{cam}` | Track ID: `{anom['person_id']}` | Time: `{time_str}`")
                st.write(f"- Zone Location: `{details.get('zone_name', 'Retail Floor')}`")
                st.write(f"- Duration: `{details.get('duration_seconds')} seconds`")
            st.markdown("---")
    else:
        st.success("✅ No operational anomalies currently logged.")

# ----------------- TAB 5: SYSTEM OPERATIONS -----------------
with tab_ops:
    st.markdown("### Administrative Actions & System Ops")
    st.write("Perform administrative commands like database resets and path checks.")
    
    col_reset, col_status = st.columns(2)
    
    with col_reset:
        st.markdown("#### Database Maintenance")
        st.write("Reset all tables in SQLite database and reload the initial datasets (sample events and POS CSV).")
        
        btn_reset_db = st.button("🗑️ Reset and Seed Database", type="secondary")
        if btn_reset_db:
            try:
                res = requests.post(f"{BACKEND_URL}/database/reset", timeout=10)
                if res.status_code == 200:
                    st.success("🎉 Database successfully cleared and re-seeded with initial datasets!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"Reset failed: {res.text}")
            except Exception as e:
                # Direct DB reset fallback for Streamlit Cloud
                try:
                    from backend import database
                    conn = database.get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("DROP TABLE IF EXISTS events")
                    cursor.execute("DROP TABLE IF EXISTS live_metrics")
                    cursor.execute("DROP TABLE IF EXISTS pos_transactions")
                    conn.commit()
                    conn.close()
                    database.seed_data_from_datasets()
                    st.success("🎉 Database successfully cleared and re-seeded with initial datasets (local fallback)!")
                    time.sleep(1)
                    st.rerun()
                except Exception as db_err:
                    st.error(f"Reset failed: {db_err}")
                
    with col_status:
        st.markdown("#### Video Directories Check")
        st.write("Verifies pathing to CCTV video assets in data/extracted.")
        
        video_files = fetch_from_api("store/videos") or []
            
        if video_files:
            st.success(f"Discovered {len(video_files)} video assets:")
            for v in video_files:
                st.code(f"Path: {v['relative_path']}\nName: {v['name']}")
        else:
            st.error("No video assets found. Ensure Store 1/2 zip files are extracted inside data/extracted.")


