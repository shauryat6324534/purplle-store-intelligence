import os
import sys
import unittest
import sqlite3
import json

# Ensure parent directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import get_db_connection, seed_data_from_datasets, get_store_summary
from backend.processor import CCTVProcessor

class TestStoreIntelligence(unittest.TestCase):
    def setUp(self):
        # Ensure database is seeded
        seed_data_from_datasets()
        
    def test_database_connection(self):
        """Test database connection and existence of tables."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Check tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row['name'] for row in cursor.fetchall()]
            
            self.assertIn("events", tables)
            self.assertIn("live_metrics", tables)
            self.assertIn("pos_transactions", tables)
        finally:
            conn.close()
        
    def test_seeded_data(self):
        """Test that data was seeded into database tables."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM events")
            event_count = cursor.fetchone()[0]
            self.assertGreater(event_count, 0, "Events table should have seeded records.")
            
            cursor.execute("SELECT COUNT(*) FROM pos_transactions")
            pos_count = cursor.fetchone()[0]
            self.assertGreater(pos_count, 0, "POS transactions table should have seeded records.")
        finally:
            conn.close()

    def test_summary_metrics(self):
        """Test store summary metric logic."""
        summary = get_store_summary()
        
        self.assertIn("total_visitors", summary)
        self.assertIn("total_revenue", summary)
        self.assertIn("conversion_rate_percentage", summary)
        self.assertIn("brand_revenue", summary)
        
        self.assertGreater(summary["total_visitors"], 0)
        self.assertGreater(summary["total_revenue"], 0.0)
        self.assertGreater(len(summary["brand_revenue"]), 0)

    def test_yolo_model_initialization(self):
        """Test that YOLOv8 processor initializes without error."""
        # We initialize with a fake path to make sure the YOLO library and weights load
        # We don't process a video in unit test to avoid long execution times
        processor = CCTVProcessor(
            video_path="dummy.mp4",
            camera_id="cam_test",
            crowd_threshold=3,
            loitering_threshold_sec=10.0
        )
        self.assertIsNotNone(processor.model)
        self.assertEqual(processor.camera_id, "cam_test")
        self.assertEqual(processor.crowd_threshold, 3)

if __name__ == "__main__":
    print("Running Store Intelligence System Verification Tests...")
    unittest.main()
