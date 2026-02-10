import threading
import logging
import requests
from typing import Optional, Any


class HAClient:
    """Synchronous client for Home Assistant REST API."""
    
    def __init__(self, url: str = "", token: str = ""):
        self.url = url.rstrip('/')
        self.token = token
        self._session: Optional[requests.Session] = None
        self._lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
    
    def configure(self, url: str, token: str):
        """Update connection settings."""
        with self._lock:
            self.url = url.rstrip('/')
            self.token = token
            # Reset session on config change
            if self._session:
                self._session.close()
                self._session = None
    
    @property
    def headers(self) -> dict:
        """Return authorization headers."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def _get_session(self) -> requests.Session:
        """Get or create requests session."""
        with self._lock:
            if self._session is None:
                self._session = requests.Session()
                # Headers are set on the session object, so we likely don't need to lock 'headers' property access
                # but 'self.token' access inside 'headers' property is technically shared state, 
                # though strings are immutable.
                self._session.headers.update(self.headers)
            return self._session
    
    def close(self):
        """Close the HTTP session."""
        with self._lock:
            if self._session:
                self._session.close()
                self._session = None
    
    def test_connection(self) -> tuple[bool, str]:
        """
        Test connection to Home Assistant.
        Returns (success, message).
        """
        # We need a local copy of url/token to be safe outside the lock for the checks
        # or just hold the lock?
        # Let's just use the properties, they are atomic enough for this check.
        if not self.url or not self.token:
            return False, "URL and token are required"
        
        try:
            session = self._get_session()
            # Session usage is thread-safe (requests)
            response = session.get(
                f"{self.url}/api/",
                timeout=5
            )
            if response.status_code == 200:
                return True, "Connected"
            elif response.status_code == 401:
                return False, "Invalid access token"
            else:
                return False, f"HTTP {response.status_code}"
        except requests.RequestException as e:
            self.logger.error(f"Connection test error: {e}")
            return False, f"Connection error: {e}"
    
    def get_entities(self) -> list[dict]:
        """
        Fetch all entities.
        Returns list of state objects.
        """
        try:
            session = self._get_session()
            response = session.get(
                f"{self.url}/api/states",
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            self.logger.error(f"Error fetching entities: {e}")
            return []
    
    def get_state(self, entity_id: str) -> Optional[dict]:
        """
        Get state of a specific entity.
        Returns entity state object or None.
        """
        try:
            session = self._get_session()
            response = session.get(
                f"{self.url}/api/states/{entity_id}",
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            self.logger.error(f"Error fetching state for {entity_id}: {e}")
            return None
    
    def call_service(
        self,
        domain: str,
        service: str,
        entity_id: Optional[str] = None,
        data: Optional[dict] = None
    ) -> bool:
        """
        Call a service.
        Returns True if successful.
        """
        try:
            payload = data or {}
            if entity_id:
                payload["entity_id"] = entity_id
            
            session = self._get_session()
            response = session.post(
                f"{self.url}/api/services/{domain}/{service}",
                json=payload,
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Service call failed for {domain}.{service}: {e}")
            return False
    
    def get_services(self) -> dict:
        """
        Get available services from Home Assistant.
        Returns dict of domain -> services.
        """
        try:
            session = self._get_session()
            response = session.get(
                f"{self.url}/api/services",
                timeout=10
            )
            if response.status_code == 200:
                services = response.json()
                # Convert to dict format
                result = {}
                for item in services:
                    domain = item.get('domain', '')
                    result[domain] = list(item.get('services', {}).keys())
                return result
            return {}
        except Exception as e:
            self.logger.error(f"Error fetching services: {e}")
            return {}
    
    def get_camera_image(self, entity_id: str) -> Optional[bytes]:
        """
        Fetch camera snapshot image.
        Returns raw image bytes or None on error.
        """
        try:
            session = self._get_session()
            response = session.get(
                f"{self.url}/api/camera_proxy/{entity_id}",
                timeout=10
            )
            if response.status_code == 200:
                return response.content
            return None
        except Exception as e:
            self.logger.error(f"Error fetching camera image for {entity_id}: {e}")
            return None
    
    def stream_camera(self, entity_id: str) -> Optional[Any]:
        """
        Start a camera stream (MJPEG).
        Returns a requests.Response object (stream=True) or None.
        Caller must close the response.
        """
        try:
            session = self._get_session()
            # Use camera_proxy_stream for MJPEG stream
            response = session.get(
                f"{self.url}/api/camera_proxy_stream/{entity_id}",
                stream=True,
                timeout=10 
            )
            if response.status_code == 200:
                return response
            return None
        except Exception as e:
            self.logger.error(f"Stream start error: {e}")
            return None
