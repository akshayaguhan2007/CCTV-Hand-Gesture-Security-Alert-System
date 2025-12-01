import sqlite3
import json
import csv
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
from pathlib import Path

class AdvancedLogger:
    def __init__(self, db_path: str = 'database.db', log_dir: str = 'logs'):
        self.db_path = db_path
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # Setup logging
        self.logger = logging.getLogger(__name__)
        self.setup_database()

        # Session tracking
        self.current_session_id = None
        self.session_start_time = None

    def setup_database(self):
        """Initialize enhanced database schema"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Enhanced logs table with more detailed information
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS gesture_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    gesture TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    hand_id INTEGER,
                    bbox TEXT,  -- JSON string of bounding box coordinates
                    center_x INTEGER,
                    center_y INTEGER,
                    landmarks TEXT,  -- JSON string of hand landmarks
                    frame_path TEXT,  -- Path to captured frame if available
                    metadata TEXT,  -- JSON string for additional metadata
                    duration REAL DEFAULT 0,  -- How long gesture was held
                    stability REAL DEFAULT 0  -- Gesture stability score
                )
            ''')

            # Sessions table for tracking user sessions
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    total_detections INTEGER DEFAULT 0,
                    unique_gestures TEXT,  -- JSON array of unique gestures
                    metadata TEXT  -- JSON string for session metadata
                )
            ''')

            # System events table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_data TEXT,  -- JSON string of event data
                    severity TEXT DEFAULT 'info'
                )
            ''')

            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_gesture_timestamp ON gesture_logs(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_gesture_session ON gesture_logs(session_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_gesture_gesture ON gesture_logs(gesture)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_start ON sessions(start_time)')

            conn.commit()

    def start_session(self, session_id: Optional[str] = None) -> str:
        """Start a new logging session"""
        if session_id:
            self.current_session_id = session_id
        else:
            self.current_session_id = datetime.now().strftime('%Y%m%d_%H%M%S')

        self.session_start_time = datetime.now()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO sessions (id, start_time) VALUES (?, ?)',
                (self.current_session_id, self.session_start_time.isoformat())
            )
            conn.commit()

        self.logger.info(f"Started logging session: {self.current_session_id}")
        return self.current_session_id

    def end_session(self):
        """End the current logging session"""
        if not self.current_session_id:
            return

        end_time = datetime.now()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE sessions SET end_time = ? WHERE id = ?',
                (end_time.isoformat(), self.current_session_id)
            )
            conn.commit()

        self.logger.info(f"Ended logging session: {self.current_session_id}")
        self.current_session_id = None
        self.session_start_time = None

    def log_gesture(self, gesture_data: Dict[str, Any]):
        """Log a gesture detection with enhanced data"""
        if not self.current_session_id:
            self.start_session()

        timestamp = datetime.now()

        # Prepare data for database
        log_entry = {
            'session_id': self.current_session_id,
            'timestamp': timestamp.isoformat(),
            'gesture': gesture_data.get('gesture', 'Unknown'),
            'confidence': gesture_data.get('confidence', 0.0),
            'hand_id': gesture_data.get('hand_id', 0),
            'bbox': json.dumps(gesture_data.get('bbox', [])),
            'center_x': gesture_data.get('center', [0, 0])[0],
            'center_y': gesture_data.get('center', [0, 0])[1],
            'landmarks': json.dumps(gesture_data.get('landmarks', [])),
            'frame_path': gesture_data.get('frame_path', ''),
            'metadata': json.dumps(gesture_data.get('metadata', {})),
            'duration': gesture_data.get('duration', 0.0),
            'stability': gesture_data.get('stability', 0.0)
        }

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO gesture_logs (
                    session_id, timestamp, gesture, confidence, hand_id,
                    bbox, center_x, center_y, landmarks, frame_path, metadata, duration, stability
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                log_entry['session_id'], log_entry['timestamp'], log_entry['gesture'],
                log_entry['confidence'], log_entry['hand_id'], log_entry['bbox'],
                log_entry['center_x'], log_entry['center_y'], log_entry['landmarks'],
                log_entry['frame_path'], log_entry['metadata'], log_entry['duration'],
                log_entry['stability']
            ))
            conn.commit()

        # Also log to system events
        self.log_system_event('gesture_detected', {
            'gesture': log_entry['gesture'],
            'confidence': log_entry['confidence'],
            'session_id': log_entry['session_id']
        })

        self.logger.info(f"Logged gesture: {log_entry['gesture']} (confidence: {log_entry['confidence']:.2f})")

    def log_system_event(self, event_type: str, event_data: Dict[str, Any], severity: str = 'info'):
        """Log system events"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO system_events (timestamp, event_type, event_data, severity) VALUES (?, ?, ?, ?)',
                (datetime.now().isoformat(), event_type, json.dumps(event_data), severity)
            )
            conn.commit()

    def get_recent_logs(self, limit: int = 50, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent gesture logs"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if session_id:
                cursor.execute(
                    'SELECT * FROM gesture_logs WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?',
                    (session_id, limit)
                )
            else:
                cursor.execute('SELECT * FROM gesture_logs ORDER BY timestamp DESC LIMIT ?', (limit,))

            rows = cursor.fetchall()

        logs = []
        for row in rows:
            log_entry = dict(row)
            # Parse JSON fields
            for json_field in ['bbox', 'landmarks', 'metadata']:
                if log_entry.get(json_field):
                    try:
                        log_entry[json_field] = json.loads(log_entry[json_field])
                    except:
                        log_entry[json_field] = {}
            logs.append(log_entry)

        return logs

    def get_session_stats(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics for a session or all sessions"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if session_id:
                # Stats for specific session
                cursor.execute('SELECT COUNT(*) FROM gesture_logs WHERE session_id = ?', (session_id,))
                total_detections = cursor.fetchone()[0]

                cursor.execute(
                    'SELECT gesture, COUNT(*) as count FROM gesture_logs WHERE session_id = ? GROUP BY gesture',
                    (session_id,)
                )
                gesture_counts = dict(cursor.fetchall())

                cursor.execute(
                    'SELECT AVG(confidence) FROM gesture_logs WHERE session_id = ?',
                    (session_id,)
                )
                avg_confidence = cursor.fetchone()[0] or 0

                return {
                    'session_id': session_id,
                    'total_detections': total_detections,
                    'gesture_counts': gesture_counts,
                    'average_confidence': avg_confidence,
                    'unique_gestures': len(gesture_counts)
                }
            else:
                # Overall stats
                cursor.execute('SELECT COUNT(*) FROM gesture_logs')
                total_detections = cursor.fetchone()[0]

                cursor.execute('SELECT COUNT(DISTINCT session_id) FROM gesture_logs')
                total_sessions = cursor.fetchone()[0]

                cursor.execute('SELECT gesture, COUNT(*) as count FROM gesture_logs GROUP BY gesture ORDER BY count DESC')
                gesture_counts = dict(cursor.fetchall())

                cursor.execute('SELECT AVG(confidence) FROM gesture_logs')
                avg_confidence = cursor.fetchone()[0] or 0

                return {
                    'total_detections': total_detections,
                    'total_sessions': total_sessions,
                    'gesture_counts': gesture_counts,
                    'average_confidence': avg_confidence,
                    'unique_gestures': len(gesture_counts)
                }

    def export_logs(self, format_type: str = 'csv', filename: Optional[str] = None,
                   session_id: Optional[str] = None) -> str:
        """Export logs to CSV or JSON format"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"gesture_logs_{timestamp}.{format_type}"

        filepath = self.log_dir / filename

        logs = self.get_recent_logs(limit=10000, session_id=session_id)  # Export up to 10k logs

        if format_type.lower() == 'csv':
            self._export_csv(logs, filepath)
        elif format_type.lower() == 'json':
            self._export_json(logs, filepath)
        else:
            raise ValueError(f"Unsupported export format: {format_type}")

        self.logger.info(f"Exported {len(logs)} logs to {filepath}")
        return str(filepath)

    def _export_csv(self, logs: List[Dict], filepath: Path):
        """Export logs to CSV format"""
        if not logs:
            return

        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = logs[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(logs)

    def _export_json(self, logs: List[Dict], filepath: Path):
        """Export logs to JSON format"""
        with open(filepath, 'w', encoding='utf-8') as jsonfile:
            json.dump(logs, jsonfile, indent=2, default=str)

    def clear_old_logs(self, days_to_keep: int = 30):
        """Clear logs older than specified days"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'DELETE FROM gesture_logs WHERE timestamp < ?',
                (cutoff_date.isoformat(),)
            )
            deleted_count = cursor.rowcount
            conn.commit()

        self.logger.info(f"Cleared {deleted_count} old log entries")
        return deleted_count

    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get currently active sessions"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM sessions WHERE end_time IS NULL ORDER BY start_time DESC')
            rows = cursor.fetchall()

        sessions = []
        for row in rows:
            session_data = dict(row)
            # Get recent activity for this session
            cursor.execute(
                'SELECT COUNT(*) FROM gesture_logs WHERE session_id = ? AND timestamp > datetime("now", "-5 minutes")',
                (session_data['id'],)
            )
            recent_activity = cursor.fetchone()[0]
            session_data['recent_activity'] = recent_activity
            sessions.append(session_data)

        return sessions
