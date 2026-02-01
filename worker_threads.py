"""
Worker Threads for Prism Desktop
"""

import logging
import asyncio # Keep in case other threads need it, but removing from these specific ones
from PyQt6.QtCore import QThread, pyqtSignal
from ha_client import HAClient

class EntityFetchThread(QThread):
    """Background thread for fetching entities."""
    
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def __init__(self, url: str, token: str):
        super().__init__()
        self.url = url
        self.token = token
    
    def run(self):
        """Fetch entities in background."""
        try:
            client = HAClient(self.url, self.token)
            entities = client.get_entities()
            client.close()
            self.finished.emit(entities)
        except Exception as e:
            self.error.emit(str(e))


class ConnectionTestThread(QThread):
    """Background thread for testing connection."""
    
    finished = pyqtSignal(bool, str)
    
    def __init__(self, url: str, token: str):
        super().__init__()
        self.url = url
        self.token = token
    
    def run(self):
        """Test connection in background."""
        try:
            client = HAClient(self.url, self.token)
            success, message = client.test_connection()
            client.close()
            self.finished.emit(success, message)
        except Exception as e:
            self.finished.emit(False, str(e))
