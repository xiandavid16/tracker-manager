import socket
import requests
import time
from concurrent.futures import ThreadPoolExecutor, Future
from typing import List
from urllib.parse import urlparse
from models.tracker_models import Tracker
from config import Config
import logging
from requests.adapters import HTTPAdapter  
from urllib3.util.retry import Retry       
from network.interface_bind import InterfaceBinder

logger = logging.getLogger(__name__)

class TrackerValidator:
    """Handles tracker validation logic"""
    
    def __init__(self, config: Config):
        self.config = config
        self.user_agent = "TrackerValidator/1.0"
        self._should_stop = False
        self._futures: List[Future] = []
        self.interface_binder = InterfaceBinder()
        self.bound_interface = None
        self.current_external_ip = "Unknown"
        self.is_validating = False
    
    def set_network_interface(self, interface_name):
        """Set specific network interface for validation"""
        self.bound_interface = interface_name
        # Update external IP when interface changes
        if interface_name:
            self._update_external_ip()
    
    def get_external_ip(self):
        """Get the current external IP"""
        return self.current_external_ip
    
    def _update_external_ip(self):
        """Update the external IP for the current interface"""
        try:
            with requests.Session() as session:
                if self.bound_interface:
                    session = self.interface_binder.bind_to_interface(session, self.bound_interface)
                
                response = session.get('https://httpbin.org/ip', timeout=5)
                ip_data = response.json()
                self.current_external_ip = ip_data.get('origin', 'Unknown')
                logger.info(f"🔍 External IP via {self.bound_interface}: {self.current_external_ip}")
        except Exception as e:
            self.current_external_ip = f"Check failed: {e}"
            logger.warning(f"Could not determine external IP: {e}")
    
    def stop_validation(self):
        """Signal to stop validation"""
        logger.info("Stopping validation")
        self._should_stop = True
        self.is_validating = False  # ADD THIS LINE
        for future in self._futures:
            future.cancel()
    
    def reset_stop_flag(self):
        """Reset stop flag for new validation run"""
        self._should_stop = False
        self.is_validating = True  # ADD THIS LINE
        self._futures.clear()
    
    def validate_batch(self, trackers: List[Tracker]) -> List[Tracker]:
        """Validate multiple trackers in parallel"""
        max_workers = self.config.get("validation.max_workers", 10)
        
        # Set validating state
        self.is_validating = True
        
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Store futures for potential cancellation
                self._futures = [executor.submit(self.validate, tracker) for tracker in trackers]
                
                results = []
                for future in self._futures:
                    if self._should_stop:
                        logger.info("Validation stopped during batch processing")
                        break
                    try:
                        result = future.result(timeout=self.config.get("validation.timeout", 10) + 5)
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Validation task failed: {e}")
                
                return results
        finally:
            # Always reset validating state when done
            self.is_validating = False
    
    def validate(self, tracker: Tracker) -> Tracker:
        """Validate a single tracker"""
        if self._should_stop:
            tracker.error = "Validation stopped by user"
            return tracker
            
        try:
            start_time = time.time()
            
            if tracker.url.startswith('udp://'):
                tracker.tracker_type = 'udp'
                tracker.alive = self._validate_udp_tracker(tracker.url)
            elif tracker.url.startswith(('http://', 'https://')):
                tracker.tracker_type = 'http'
                tracker.alive = self._validate_http_tracker(tracker.url)
            elif tracker.url.startswith('magnet:'):
                tracker.tracker_type = 'magnet'
                tracker.alive = True
            
            tracker.response_time = time.time() - start_time
            logger.debug(f"Validated {tracker.url}: {tracker.alive} ({tracker.response_time:.2f}s)")
            
        except Exception as e:
            tracker.error = str(e)
            tracker.alive = False
            logger.error(f"Error validating {tracker.url}: {e}")
        
        return tracker
    
    def _validate_udp_tracker(self, url: str) -> bool:
        """Validate UDP tracker with proper error handling"""
        sock = None
        try:
            parsed = urlparse(url)
            default_port = self.config.get("trackers.default_ports.udp", 6969)
            host, port = parsed.hostname, parsed.port or default_port
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.config.get("validation.socket_timeout", 5))
            
            try:
                sock.connect((host, port))
                # UDP tracker protocol handshake
                connection_id = b'\x00\x00\x04\x17\x27\x10\x19\x80'
                action = b'\x00\x00\x00\x00'
                transaction_id = b'\x00\x00\x00\x01'
                
                message = connection_id + action + transaction_id
                sock.sendto(message, (host, port))
                
                # Safe receive with size validation
                data, addr = sock.recvfrom(16)
                return len(data) >= 16
                
            except socket.timeout:
                return False
            except ConnectionRefusedError:
                return False
                
        except Exception as e:
            logger.debug(f"UDP validation failed for {url}: {e}")
            return False
        finally:
            if sock:
                sock.close()

    def _validate_http_tracker(self, url: str) -> bool:
        """Validate HTTP tracker with proper resource cleanup"""
        try:
            # Use context manager for automatic cleanup
            with requests.Session() as session:
                session.headers.update({'User-Agent': self.user_agent})
                
                # Apply interface binding if set
                if self.bound_interface:
                    session = self.interface_binder.bind_to_interface(session, self.bound_interface)
                    logger.info(f"🔒 Validating {url} through interface: {self.bound_interface}")
                
                # Try HEAD first
                try:
                    response = session.head(url, timeout=self.config.get("validation.timeout", 10), allow_redirects=True)
                    if 200 <= response.status_code < 300:
                        return True
                except requests.RequestException:
                    pass
                
                # Fallback to GET
                try:
                    response = session.get(url, timeout=self.config.get("validation.timeout", 10), allow_redirects=True)
                    return 200 <= response.status_code < 300
                except requests.RequestException:
                    return False
                    
        except Exception as e:
            logger.debug(f"HTTP validation failed for {url}: {e}")
            return False
            
class OptimizedValidator(TrackerValidator):
    """Validator with connection pooling and optimizations"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.setup_session_pooling()
    
    def setup_session_pooling(self):
        """Configure requests session with connection pooling"""
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy, 
            pool_connections=10, 
            pool_maxsize=10
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Apply interface binding to the persistent session if set
        if self.bound_interface:
            self.session = self.interface_binder.bind_to_interface(self.session, self.bound_interface)

class SafeTrackerValidator(TrackerValidator):
    """Validator with comprehensive error handling"""
    
    def validate_with_fallback(self, tracker: Tracker) -> Tracker:
        """Validate with multiple fallback strategies"""
        try:
            return self.validate(tracker)
        except ConnectionError:
            # Retry with increased timeout
            return self.validate_with_increased_timeout(tracker)
        except Exception as e:
            logger.error(f"Validation failed for {tracker.url}: {e}")
            tracker.error = f"Validation error: {e}"
            tracker.alive = False
            return tracker
    
    def validate_with_increased_timeout(self, tracker: Tracker) -> Tracker:
        """Retry validation with longer timeout"""
        original_timeout = self.config.get("validation.timeout")
        self.config.set("validation.timeout", original_timeout * 2)
        try:
            return self.validate(tracker)
        finally:
            self.config.set("validation.timeout", original_timeout)

def validate_large_batches(validator: TrackerValidator, trackers: List[Tracker], chunk_size=50):
    """Validate large lists in chunks to prevent resource exhaustion"""
    for i in range(0, len(trackers), chunk_size):
        chunk = trackers[i:i + chunk_size]
        chunk_results = validator.validate_batch(chunk)
        yield chunk_results
        if validator._should_stop:
            break