"""
Home Assistant WebSocket Client
Handles real-time state updates and notifications.
"""

import asyncio
import time
import json
import aiohttp
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal, QThread
import threading
import logging


class HAWebSocket(QObject):
    """WebSocket client for Home Assistant real-time updates."""
    
    # Signals
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    state_changed = pyqtSignal(str, dict)  # entity_id, new_state
    notification_received = pyqtSignal(str, str)  # title, message
    error = pyqtSignal(str)
    
    def __init__(self, url: str = "", token: str = ""):
        super().__init__()
        self.url = url.rstrip('/')
        self.token = token
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._running = False
        self._message_id = 0
        self._subscribed_entities: set[str] = set()
        self._config_lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
    
    def configure(self, url: str, token: str):
        """Update connection settings thread-safely."""
        with self._config_lock:
            self.url = url.rstrip('/')
            self.token = token
    
    def subscribe_entity(self, entity_id: str):
        """Add entity to subscription list."""
        self._subscribed_entities.add(entity_id)
    
    def unsubscribe_entity(self, entity_id: str):
        """Remove entity from subscription list."""
        self._subscribed_entities.discard(entity_id)
    
    def clear_subscriptions(self):
        """Clear all entity subscriptions."""
        self._subscribed_entities.clear()
    
    def _next_id(self) -> int:
        """Get next message ID."""
        self._message_id += 1
        return self._message_id
    
    def request_stop(self):
        """Thread-safe stop request."""
        self._running = False
    
    async def _send(self, data: dict):
        """Send message to WebSocket."""
        if self._ws and not self._ws.closed:
            await self._ws.send_json(data)
    
    async def connect(self):
        """Connect to Home Assistant WebSocket."""
        # Capture config under lock
        with self._config_lock:
            current_url = self.url
            current_token = self.token
            
        if not current_url or not current_token:
            self.error.emit("URL and token are required")
            return
        
        ws_url = current_url.replace('http://', 'ws://').replace('https://', 'wss://')
        ws_url = f"{ws_url}/api/websocket"
        
        try:
            self._session = aiohttp.ClientSession()
            self._ws = await self._session.ws_connect(ws_url)
            self._running = True
            
            # Wait for auth_required
            msg = await self._ws.receive_json()
            if msg.get('type') != 'auth_required':
                raise Exception("Unexpected message type")
            
            # Send auth
            await self._send({
                "type": "auth",
                "access_token": current_token
            })
            
            # Wait for auth_ok
            msg = await self._ws.receive_json()
            if msg.get('type') != 'auth_ok':
                raise Exception(f"Authentication failed: {msg.get('message', 'Unknown error')}")
            
            self.connected.emit()
            
            # Subscribe to state changes
            await self._send({
                "id": self._next_id(),
                "type": "subscribe_events",
                "event_type": "state_changed"
            })
            
            # Subscribe to call_service events (for catching notification creates)
            await self._send({
                "id": self._next_id(),
                "type": "subscribe_events",
                "event_type": "call_service"
            })
            
            # Start message loop
            await self._message_loop()
            
        except Exception as e:
            if self._running:  # Only emit error if not stopping
                self.error.emit(str(e))
        finally:
            await self._cleanup()
    
    async def _message_loop(self):
        """Process incoming WebSocket messages."""
        while self._running and self._ws and not self._ws.closed:
            try:
                msg = await asyncio.wait_for(
                    self._ws.receive(),
                    timeout=5  # Short timeout to check _running flag more often
                )
                
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    await self._handle_message(data)
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break
                    
            except asyncio.TimeoutError:
                # Check if we should stop
                if not self._running:
                    break
                # Send ping to keep connection alive
                if self._ws and not self._ws.closed:
                    try:
                        await self._send({"id": self._next_id(), "type": "ping"})
                    except:
                        break
            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._running:
                    self.error.emit(str(e))
                break
    
    async def _handle_message(self, data: dict):
        """Handle incoming message."""
        msg_type = data.get('type', '')
        
        if msg_type == 'event':
            event = data.get('event', {})
            event_type = event.get('event_type', '')
            event_data = event.get('data', {})
            
            if event_type == 'state_changed':
                entity_id = event_data.get('entity_id', '')
                new_state = event_data.get('new_state', {})
                
                # Check for persistent_notification entities
                if entity_id.startswith('persistent_notification.'):
                    # New notification created
                    if new_state:
                        attrs = new_state.get('attributes', {})
                        title = attrs.get('title', 'Home Assistant')
                        message = attrs.get('message', new_state.get('state', ''))
                        if message:
                            self.notification_received.emit(title, message)
                
                # Only emit state changes for subscribed entities or all if none specified
                if not self._subscribed_entities or entity_id in self._subscribed_entities:
                    self.state_changed.emit(entity_id, new_state)
            
            elif event_type == 'call_service':
                # Check for persistent_notification.create service calls
                domain = event_data.get('domain', '')
                service = event_data.get('service', '')
                service_data = event_data.get('service_data', {})
                
                if domain == 'persistent_notification' and service == 'create':
                    title = service_data.get('title', 'Home Assistant')
                    message = service_data.get('message', '')
                    if message:
                        self.notification_received.emit(title, message)
    
    async def _cleanup(self):
        """Clean up WebSocket connection."""
        self._running = False
        try:
            if self._ws and not self._ws.closed:
                await self._ws.close()
        except:
            pass
        try:
            if self._session and not self._session.closed:
                await self._session.close()
        except:
            pass
        # Only emit if object still exists
        try:
            self.disconnected.emit()
        except RuntimeError:
            # Object was deleted
            pass
    
    async def disconnect(self):
        """Disconnect from WebSocket."""
        self._running = False
        try:
            await self._cleanup()
        except RuntimeError:
            # Object was deleted
            pass


class WebSocketThread(QThread):
    """Thread for running WebSocket client."""
    
    def __init__(self, ws_client: HAWebSocket):
        super().__init__()
        self.ws_client = ws_client
        self.logger = logging.getLogger(__name__)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_requested = False
    
    def run(self):
        """Run the WebSocket client with auto-reconnection."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        backoff = 1
        max_backoff = 30
        
        try:
            while not self._stop_requested:
                try:
                    # Reset backoff on successful run (if it stays connected for a bit)
                    start_time = time.time()
                    
                    # Run client connection
                    self._loop.run_until_complete(self.ws_client.connect())
                    
                    # If we are here, connect() returned (disconnect or error)
                    if self._stop_requested:
                        break
                        
                    # Check if connection was short-lived (immediate failure)
                    if time.time() - start_time > 10:
                        backoff = 1  # Reset backoff if we were connected for >10s
                    
                    self.logger.warning(f"WebSocket disconnected. Reconnecting in {backoff}s...")
                    self.ws_client.error.emit(f"Disconnected. Reconnecting in {backoff}s...")
                    
                    # Wait for backoff or stop
                    # We can't use time.sleep or QThread.sleep effectively with stop signal
                    # So we use a small loop
                    for _ in range(backoff * 10):
                        if self._stop_requested: break
                        self.msleep(100)
                        
                    # Exponential backoff
                    backoff = min(backoff * 2, max_backoff)
                    
                except Exception as e:
                    self.logger.error(f"WebSocket Thread Error: {e}")
                    if self._stop_requested: break
                    self.msleep(1000)
                    
        finally:
            try:
                # Clean up pending tasks
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()
                if pending:
                    self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                self._loop.close()
            except:
                pass
    
    def stop(self):
        """Stop the WebSocket thread gracefully (non-blocking)."""
        self.logger.info("WebSocketThread.stop() called")
        self._stop_requested = True
        
        # Request websocket to stop
        self.ws_client.request_stop()
        
        # Try to disconnect via event loop if it's running
        if self._loop and self._loop.is_running():
            try:
                # Schedule disconnect but don't wait synchronously
                asyncio.run_coroutine_threadsafe(
                    self.ws_client.disconnect(),
                    self._loop
                )
            except:
                pass
        
        # Signal thread to quit event loop
        self.quit()
