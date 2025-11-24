import threading
import time
import logging
from typing import Callable, Any, Tuple, List, Dict
import csv  
import io

from models import TrackerDatabase, Tracker, TrackerCollection, TrackerStats
from config import Config
from services.tracker_parser import TrackerParser
from services.tracker_validator import TrackerValidator

logger = logging.getLogger(__name__)

class MainController:
    """Main application controller (MVC pattern)"""
    
    def __init__(self):
        self.config = Config()
        self.trackers = TrackerCollection()
        self.parser = TrackerParser()
        self.validator = TrackerValidator(self.config)
        self.database = TrackerDatabase()
        
        self.view = None  # Will be set by the view
        self.validation_thread = None
        self.is_validating = False
    
    def set_view(self, view):
        """Set the view reference"""
        self.view = view
    
    # Add these network interface methods:
    def get_network_interfaces(self):
        """Get available network interfaces"""
        return self.validator.interface_binder.detect_interfaces()
    
    def set_validation_interface(self, interface_name):
        """Set network interface for validation"""
        self.validator.set_network_interface(interface_name)
        self.config.set("validation.network_interface", interface_name)
    
    def is_linux_system(self):
        """Check if running on Linux"""
        return self.validator.interface_binder.is_linux()
    
    def find_duplicates(self, text: str) -> dict:
        """Find and remove duplicate trackers"""
        if not text.strip():
            raise ValueError("Please paste some tracker URLs first!")
        
        all_trackers = self.parser.extract_trackers_from_text(text)
        if not all_trackers:
            raise ValueError("No valid tracker URLs found!")
        
        self.trackers.unique_urls = self.parser.remove_duplicates(all_trackers)
        
        return {
            'total': len(all_trackers),
            'unique': len(self.trackers.unique_urls),
            'duplicates': len(all_trackers) - len(self.trackers.unique_urls)
        }
    
    def start_validation(self):
        """Start tracker validation"""
        if not self.trackers.unique_urls:
            raise ValueError("No trackers to validate! Find duplicates first.")
        
        if self.is_validating:
            raise ValueError("Validation already in progress.")
        
        self.is_validating = True
        self.validator.reset_stop_flag()
        self.validator.is_validating = True  # ADD THIS LINE
        self.trackers.validation_results.clear()
        
        # Convert URLs to Tracker objects
        trackers_to_validate = [Tracker(url) for url in self.trackers.unique_urls]
        
        # Start validation in background thread
        self.validation_thread = threading.Thread(target=self._run_validation, args=(trackers_to_validate,), daemon=True)
        self.validation_thread.start()
        
        logger.info(f"Started validation of {len(trackers_to_validate)} trackers")
    
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
            
            # Validation sessions table - ADD THIS
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS validation_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_trackers INTEGER DEFAULT 0,
                    working_trackers INTEGER DEFAULT 0,
                    duration REAL DEFAULT 0.0
                )
            ''')
            
            # Favorites table - ADD THIS
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

    def _run_validation(self, trackers: list):
        """Run validation in background thread with progress and proper stopping"""
        try:
            start_time = time.time()
            total = len(trackers)
            results = []
            
            for i, tracker in enumerate(trackers):
                # Check if validation should stop
                if getattr(self.validator, '_should_stop', False):
                    logger.info("Validation stopped by user")
                    break
                    
                result = self.validator.validate(tracker)
                results.append(result)
                
                # Stream result to UI
                if self.view:
                    self.view.safe_gui_update(self.view.append_tracker_result, result)
                
                # Update progress
                progress = (i + 1) / total * 100
                if self.view:
                    self.view.safe_gui_update(self.view.update_progress, progress, i+1, total)
            
            # Update the trackers collection with results
            self.trackers.validation_results = results
            
            elapsed = time.time() - start_time
            working_count = len([r for r in results if r.alive])
            
            # Save to database
            if hasattr(self, 'database') and self.database:
                for tracker in results:
                    self.database.save_tracker_result(tracker)
                self.database.save_validation_session(
                    total_trackers=len(results),
                    working_trackers=working_count,
                    duration=elapsed
                )
            
            logger.info(f"Validation completed: {working_count}/{len(results)} working ({elapsed:.2f}s)")
            
            if self.view:
                self.view.safe_gui_update(lambda: self.view.on_validation_complete(
                    working_count, len(results), elapsed
                ))
                
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            if self.view:
                self.view.safe_gui_update(lambda: self.view.show_error(f"Validation failed: {e}"))
        finally:
            self.is_validating = False
            self.validator.is_validating = False  # ADD THIS LINE
            
    def get_tracker_history(self, limit: int = 100):
        """Get tracker validation history"""
        return self.database.get_tracker_history(limit)
    
    def get_reliable_trackers(self, min_success_rate: float = 0.8, min_checks: int = 3):
        """Get reliable trackers based on historical data"""
        return self.database.get_reliable_trackers(min_success_rate, min_checks)
    
    def add_to_favorites(self, tracker_url: str, notes: str = ""):
        """Add tracker to favorites"""
        normalized_url = Tracker.normalize_tracker_url(tracker_url)
        # First get or create tracker record
        tracker = Tracker(tracker_url)
        tracker_id = self.database.save_tracker_result(tracker)
        self.database.add_to_favorites(tracker_id, notes)
    
    def get_favorites(self):
        """Get favorite trackers"""
        return self.database.get_favorites()
    
    def get_validation_stats(self):
        """Get validation statistics"""
        history = self.database.get_tracker_history(limit=1000)
        if not history:
            return {}
        
        total_checks = sum(t.check_count for t in history)
        successful_checks = sum(t.success_count for t in history)
        avg_success_rate = successful_checks / total_checks if total_checks > 0 else 0
        
        return {
            'total_trackers_tested': len(history),
            'total_validation_checks': total_checks,
            'overall_success_rate': avg_success_rate,
            'most_reliable': self.database.get_reliable_trackers(limit=5)
        }

    def stop_validation(self):
        """Stop ongoing validation"""
        if self.is_validating:
            self.validator.stop_validation()
            self.validator.is_validating = False  # ADD THIS LINE
            self.is_validating = False
            logger.info("Validation stopped by user")
    
    def export_working_trackers(self) -> str:
        """Export working trackers as text"""
        return '\n'.join(tracker.url for tracker in self.trackers.working_trackers)
    
    def export_all_results(self) -> dict:
        """Export all results as structured data"""
        return {
            'timestamp': time.time(),
            'total_trackers': len(self.trackers.validation_results),
            'working_trackers': len(self.trackers.working_trackers),
            'results': [
                {
                    'url': tracker.url,
                    'alive': tracker.alive,
                    'response_time': tracker.response_time,
                    'error': tracker.error,
                    'type': tracker.tracker_type
                }
                for tracker in self.trackers.validation_results
            ]
        }
    
    def copy_to_clipboard(self) -> str:
        """Copy working trackers to clipboard"""
        working_urls = [tracker.url for tracker in self.trackers.working_trackers]
        if not working_urls:
            raise ValueError("No working trackers to copy!")
        return '\n'.join(working_urls)

    def health_check(self) -> Tuple[bool, Dict]:
        """Perform application health checks"""
        checks = {
            'config_loaded': bool(self.config.data),
            'services_ready': all([
                hasattr(self, 'validator'),
                hasattr(self, 'parser')
            ]),
            'validation_workers': self.config.get("validation.max_workers", 0) > 0
        }
        return all(checks.values()), checks

    def load_preset(self, preset_name: str) -> List[str]:
        """Load a preset tracker list"""
        presets = self.config.get_presets()
        if preset_name in presets:
            return presets[preset_name]
        return []

    def export_multiple_formats(self, format_type: str) -> Any:
        """Export results in different formats"""
        if format_type == 'csv':
            return self.export_csv()
        elif format_type == 'yaml':
            return self.export_yaml()
        else:  # json
            return self.export_all_results()

    def export_csv(self) -> str:
        """Export as CSV string"""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['URL', 'Status', 'Response Time', 'Type', 'Error'])
        for tracker in self.trackers.validation_results:
            writer.writerow([
                tracker.url,
                'Working' if tracker.alive else 'Dead',
                f"{tracker.response_time:.2f}" if tracker.response_time else '',
                tracker.tracker_type,
                tracker.error or ''
            ])
        return output.getvalue()

    def export_yaml(self) -> str:
        """Export as YAML string"""
        import yaml
        data = self.export_all_results()
        return yaml.dump(data, default_flow_style=False)

    def get_statistics(self) -> TrackerStats:
        """Calculate tracker statistics"""
        results = self.trackers.validation_results
        working = [r for r in results if r.alive]
        dead = [r for r in results if not r.alive]
        
        response_times = [r.response_time for r in working if r.response_time]
        avg_time = sum(response_times) / len(response_times) if response_times else 0
        
        by_type = {}
        for result in results:
            by_type[result.tracker_type] = by_type.get(result.tracker_type, 0) + 1
        
        return TrackerStats(
            total=len(results),
            working=len(working),
            dead=len(dead),
            avg_response_time=avg_time,
            by_type=by_type
        )

    def batch_operations(self, operation: str, trackers: List[Tracker]) -> List[Tracker]:
        """Perform batch operations on trackers"""
        if operation == 'select_working':
            return [t for t in trackers if t.alive]
        elif operation == 'deselect_all':
            return []
        elif operation == 'select_all':
            return trackers
        return trackers