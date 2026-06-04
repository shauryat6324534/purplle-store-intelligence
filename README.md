# 🔮 Purplle Store Intelligence System

A complete CCTV Computer Vision Store Analytics MVP built for **Purplle Tech Challenge 2026 Round 2**.

This project processes CCTV video streams using **YOLOv8** to track customer density, detect behavioral anomalies (loitering and crowding), generate standard security/traffic events, and display live store conversion metrics by correlating visual traffic with POS transactions.

---

## 🚀 Key Features

- **Real-Time Person Detection & Tracking**: Uses YOLOv8 Nano to identify and assign persistent tracking IDs (`person_id`) to shoppers in video feeds.
- **Retail Events Generator**:
  - `PERSON_ENTERED`: Customer walks into a camera frame.
  - `PERSON_EXITED`: Customer leaves the frame.
  - `CROWD_ALERT`: Shopper count in frame exceeds threshold (e.g., 4+ people).
  - `LOITERING_ALERT`: Shopper remains in a zone (e.g., makeup shelves) for longer than the set threshold (e.g., 15s+).
- **SQLite Database Storage**: Automatically logs all events and current camera density states.
- **FastAPI Backend Services**: Exposes REST API endpoints (`/metrics/live`, `/events`, `/anomalies`, `/store/summary`) for integration with central retail dashboards.
- **POS Transaction Correlation**: Merges Point of Sale brand sales data to compute live store conversion rates and basket sizes.
- **Interactive Streamlit Dashboard**:
  - Beautiful visual KPI cards (glowing dark purple theme).
  - Shopper flow graphs and brand revenue bars.
  - **Live CCTV Video Processor**: Load any store camera feed, run the YOLOv8 tracker frame-by-frame, and watch the bounding boxes and events update in real time.

---

## 📁 Project Structure

```text
purplle-store-intelligence/
├── backend/
│   ├── database.py       # SQLite database initialization, queries, and seeding
│   ├── main.py           # FastAPI application endpoints & background tasks
│   └── processor.py      # YOLOv8 person tracking & events processor
├── frontend/
│   └── dashboard.py      # Streamlit analytical dashboard and CV player
├── docs/
│   └── architecture.md   # Detailed architecture and API contracts doc
├── data/
│   ├── POS - sample transactionsb1e826f.csv
│   ├── sample_eventsbe42122.jsonl
│   ├── Store 1-....zip   # Store 1 CCTV clips
│   └── Store 2-....zip   # Store 2 CCTV clips
├── requirements.txt      # Python dependencies
├── Dockerfile            # Multi-service Docker container setup
├── run.py                # Setup, extraction, and concurrent execution script
└── README.md             # This document
```

---

## 🛠️ Quickstart Guide

### Option 1: Running Locally (Recommended)

Make sure you have Python 3.8+ installed.

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Launch Services**:
   Simply run the root-level startup script. It will automatically extract the CCTV video zip archives, initialize the SQLite database, seed it with sample records, and spin up both services:
   ```bash
   python run.py
   ```

3. **Access Interfaces**:
   - **Streamlit Dashboard**: Open [http://localhost:8501](http://localhost:8501) in your browser.
   - **FastAPI Documentation (Swagger)**: Open [http://localhost:8000/docs](http://localhost:8000/docs).

---

### Option 2: Running via Docker

You can build and run the entire application inside a container:

1. **Build Docker Image**:
   ```bash
   docker build -t purplle-store-intelligence .
   ```

2. **Run Docker Container**:
   ```bash
   docker run -p 8000:8000 -p 8501:8501 purplle-store-intelligence
   ```

3. **Access Interfaces**:
   - **Dashboard**: [http://localhost:8501](http://localhost:8501)
   - **API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🔌 API Documentation Summary

The FastAPI backend exposes the following primary endpoints:

- `GET /metrics/live`: Current people count and status across all cameras.
- `GET /events`: Historical log of all retail events (with `event_type` and `camera_id` filtering).
- `GET /anomalies`: List of all `CROWD_ALERT` and `LOITERING_ALERT` incidents.
- `GET /store/summary`: Retail dashboard analytics (footfalls, total sales, conversion rate, busy hours, and brand shares).

*For more details, see the [architecture.md](file:///c:/Users/Shaurya%20Binjola/Documents/GitHub/purplle-store-intelligence/docs/architecture.md) document in the `docs/` folder.*