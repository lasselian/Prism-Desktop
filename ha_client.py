"""
Home Assistant REST API Client for Prism Desktop (Synchronous)
Handles all HTTP communication with Home Assistant using requests.
"""

import requests
from typing import Optional, Any


class HAClient:
    """Synchronous client for Home Assistant REST API."""
    
    def __init__(self, url: str = "", token: str = ""):
        self.url = url.rstrip('/')
        self.token = token
        self._session: Optional[requests.Session] = None
    
    def configure(self, url: str, token: str):
        """Update connection settings."""
        self.url = url.rstrip('/')
        self.token = token
        # Reset session on config change
        if self._session:
            self._session.close()
            self._session = None
    
    @property
    def headers(self) -> dict:
        """Get authorization headers."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def _get_session(self) -> requests.Session:
        """Get or create requests session."""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update(self.headers)
        return self._session
    
    def close(self):
        """Close the HTTP session."""
        if self._session:
            self._session.close()
            self._session = None
    
    def test_connection(self) -> tuple[bool, str]:
        """
        Test connection to Home Assistant.
        Returns (success, message).
        """
        if not self.url or not self.token:
            return False, "URL and token are required"
        
        try:
            session = self._get_session()
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
            return False, f"Connection error: {e}"
    
    def get_entities(self) -> list[dict]:
        """
        Fetch all entities from Home Assistant.
        Returns list of entity state objects.
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
        except Exception:
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
        except Exception:
            return None
    
    def call_service(
        self,
        domain: str,
        service: str,
        entity_id: Optional[str] = None,
        data: Optional[dict] = None
    ) -> bool:
        """
        Call a Home Assistant service.
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
        except Exception:
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
        except Exception:
            return {}

