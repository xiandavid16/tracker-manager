import sqlite3
from .tracker_models import Tracker
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class TrackerHistory:
    id: Optional[int] = None
    url: str = ""
    normalized_url: str = ""
    alive: bool = False
    response_time: float = 0.0
    last_checked: datetime = None
    check_count: int = 0
    success_count: int = 0
    tracker_type: str = "unknown"
    created_at: datetime = None
    updated_at: datetime = None

@dataclass
class ValidationSession:
    id: Optional[int] = None
    timestamp: datetime = None
    total_trackers: int = 0
    working_trackers: int = 0
    duration: float = 0.0

class TrackerDatabase:
    def __init__(self, db_path: str = "tracker_history.db"):
        self.db_path = db_path
        self.init_database()
    
    # ===== DATABASE INITIALIZATION METHODS =====
    
    def init_database(self):
        """Initialize database tables with proper constraints"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Trackers table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trackers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL CHECK(length(url) > 0),
                    normalized_url TEXT UNIQUE NOT NULL CHECK(length(normalized_url) > 0),
                    alive BOOLEAN DEFAULT FALSE,
                    response_time REAL DEFAULT 0.0 CHECK(response_time >= 0),
                    last_checked TIMESTAMP,
                    check_count INTEGER DEFAULT 0 CHECK(check_count >= 0),
                    success_count INTEGER DEFAULT 0 CHECK(success_count >= 0),
                    tracker_type TEXT DEFAULT 'unknown' CHECK(tracker_type IN ('http', 'https', 'udp', 'magnet', 'unknown')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CHECK(success_count <= check_count)
                )
            ''')
            
            # Validation sessions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS validation_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_trackers INTEGER DEFAULT 0,
                    working_trackers INTEGER DEFAULT 0,
                    duration REAL DEFAULT 0.0
                )
            ''')
            
            # Favorites table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tracker_id INTEGER,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tracker_id) REFERENCES trackers (id)
                )
            ''')
            
            # Create indexes for performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_normalized_url ON trackers(normalized_url)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_last_checked ON trackers(last_checked)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_favorites_tracker_id ON favorites(tracker_id)')
            
            conn.commit()
    
    def clear_all_history(self): 
        """Clear all tracker history and validation sessions"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Clear trackers table (this will cascade to favorites due to foreign key)
            cursor.execute('DELETE FROM trackers')
            
            # Clear validation sessions
            cursor.execute('DELETE FROM validation_sessions')
            
            # Reset favorites (optional - remove if you want to keep favorites)
            cursor.execute('DELETE FROM favorites')
            
            conn.commit()
        
        logger.info("All history cleared from database")

    def clear_tracker_history(self):
        """Clear only tracker history but keep favorites"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Clear trackers that are not in favorites
            cursor.execute('''
                DELETE FROM trackers 
                WHERE id NOT IN (SELECT tracker_id FROM favorites WHERE tracker_id IS NOT NULL)
            ''')
            
            # Clear validation sessions
            cursor.execute('DELETE FROM validation_sessions')
            
            conn.commit()
        
        logger.info("Tracker history cleared (favorites preserved)")

    def get_history_stats(self):
        """Get counts for confirmation dialog"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM trackers')
            tracker_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM validation_sessions') 
            session_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM favorites')
            favorite_count = cursor.fetchone()[0]
            
        return {
            'trackers': tracker_count,
            'sessions': session_count,
            'favorites': favorite_count
        }  
        
    # ===== TRACKER DATA MANAGEMENT METHODS =====
    
    def save_tracker_result(self, tracker: 'Tracker') -> int:
        """Save or update tracker validation result"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check if tracker exists
            cursor.execute(
                "SELECT id, check_count, success_count FROM trackers WHERE normalized_url = ?",
                (tracker.normalized_url,)
            )
            result = cursor.fetchone()
            
            current_time = datetime.now().isoformat()
            
            if result:
                # Update existing tracker
                tracker_id, check_count, success_count = result
                new_check_count = check_count + 1
                new_success_count = success_count + (1 if tracker.alive else 0)
                
                cursor.execute('''
                    UPDATE trackers 
                    SET alive = ?, response_time = ?, last_checked = ?, 
                        check_count = ?, success_count = ?, tracker_type = ?, updated_at = ?
                    WHERE id = ?
                ''', (
                    tracker.alive, tracker.response_time, current_time,
                    new_check_count, new_success_count, tracker.tracker_type, current_time, tracker_id
                ))
            else:
                # Insert new tracker
                cursor.execute('''
                    INSERT INTO trackers 
                    (url, normalized_url, alive, response_time, last_checked, check_count, success_count, tracker_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    tracker.url, tracker.normalized_url, tracker.alive, tracker.response_time,
                    current_time, 1, (1 if tracker.alive else 0), tracker.tracker_type
                ))
                tracker_id = cursor.lastrowid
            
            conn.commit()
            return tracker_id
    
    def get_tracker_history(self, limit: int = 100) -> List[TrackerHistory]:
        """Get recent tracker validation history"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM trackers 
                ORDER BY last_checked DESC 
                LIMIT ?
            ''', (limit,))
            
            return [TrackerHistory(**dict(row)) for row in cursor.fetchall()]
    
    def get_reliable_trackers(self, min_success_rate: float = 0.8, min_checks: int = 3) -> List[TrackerHistory]:
        """Get trackers with high reliability"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM trackers 
                WHERE check_count >= ? AND (success_count * 1.0 / check_count) >= ?
                AND alive = TRUE
                ORDER BY (success_count * 1.0 / check_count) DESC, response_time ASC
            ''', (min_checks, min_success_rate))
            
            return [TrackerHistory(**dict(row)) for row in cursor.fetchall()]
    
    # ===== VALIDATION SESSION METHODS =====
    
    def save_validation_session(self, total_trackers: int, working_trackers: int, duration: float):
        """Save validation session summary"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO validation_sessions (total_trackers, working_trackers, duration)
                VALUES (?, ?, ?)
            ''', (total_trackers, working_trackers, duration))
            conn.commit()
    
    # ===== FAVORITES MANAGEMENT METHODS =====
    
    def add_to_favorites(self, tracker_id: int, notes: str = ""):
        """Add tracker to favorites"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO favorites (tracker_id, notes)
                VALUES (?, ?)
            ''', (tracker_id, notes))
            conn.commit()
    
    def get_favorites(self) -> List[TrackerHistory]:
        """Get favorite trackers"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT t.* FROM trackers t
                JOIN favorites f ON t.id = f.tracker_id
                ORDER BY f.created_at DESC
            ''')
            
            return [TrackerHistory(**dict(row)) for row in cursor.fetchall()]