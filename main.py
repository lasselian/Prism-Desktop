"""
Prism Desktop - Home Assistant Tray Application
Main entry point and application controller.
"""

import sys
import json
import time
from pathlib import Path
from typing import Optional

from utils import get_config_path

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, pyqtSlot, QThread, QThreadPool, QRunnable

from theme_manager import ThemeManager
from ha_client import HAClient
from ha_websocket import HAWebSocket, WebSocketThread
from dashboard import Dashboard
from worker_threads import EntityFetchThread
from tray_manager import TrayManager
from notifications import NotificationManager
from input_manager import InputManager
from icons import load_mdi_font


class ServiceCallSignals(QObject):
    """Signals for ServiceCallRunnable."""
    call_complete = pyqtSignal(bool)


class ServiceCallRunnable(QRunnable):
    """Background runnable for calling HA services."""
    
    def __init__(self, client: HAClient, domain: str, service: str, entity_id: str, data: dict = None):
        super().__init__()
        self.client = client
        self.domain = domain
        self.service = service
        self.entity_id = entity_id
        self.data = data
        self.signals = ServiceCallSignals()
    
    def run(self):
        """Call the service in background."""
        try:
            # Use the shared client (thread-safe enough for requests.Session)
            result = self.client.call_service(
                self.domain, self.service, self.entity_id, self.data
            )
            self.signals.call_complete.emit(result)
        except Exception as e:
            print(f"Service call error: {e}")
            self.signals.call_complete.emit(False)


class StateFetchThread(QThread):
    """Background thread for fetching entity states (values)."""
    
    state_fetched = pyqtSignal(str, dict)
    
    def __init__(self, client: HAClient, entity_ids: list):
        super().__init__()
        self.client = client
        self.entity_ids = entity_ids
    
    def run(self):
        """Fetch states in background."""
        try:
            for entity_id in self.entity_ids:
                try:
                    state = self.client.get_state(entity_id)
                    if state:
                        self.state_fetched.emit(entity_id, state)
                except Exception as e:
                    print(f"Error fetching {entity_id}: {e}")
        except Exception as e:
            print(f"State fetch error: {e}")


class PrismDesktopApp(QObject):
    """Main application controller."""
    
    def __init__(self):
        super().__init__()
        
        # Configuration
        self.config_path = get_config_path("config.json")
        self.config = self.load_config()
        
        # Components
        self.theme_manager = ThemeManager()
        self.ha_client = HAClient()
        self.notification_manager = NotificationManager()
        self.input_manager = InputManager()
        
        # Thread Pool
        self.thread_pool = QThreadPool()
        print(f"Thread Pool Max Threads: {self.thread_pool.maxThreadCount()}")
        
        # UI Components
        self.dashboard: Optional[Dashboard] = None
        self.tray_manager: Optional[TrayManager] = None
        
        # WebSocket - will be created fresh each time
        self._ha_websocket: Optional[HAWebSocket] = None
        self._ws_thread: Optional[WebSocketThread] = None
        
        # Background threads - keep references to prevent GC
        self._fetch_thread: Optional[StateFetchThread] = None
        self._entity_list_thread: Optional[EntityFetchThread] = None # For editor
        
        # Cache for entity list (for editor)
        self._available_entities: list[dict] = []
        
        # Debounce tracking - prevent rapid clicks
        self._last_click_time: dict[str, float] = {}  # entity_id -> timestamp
        self._click_cooldown = 0.5  # seconds between clicks for same entity
        
        # Initialize
        self.init_theme()
        self.init_ha_client()
        self.init_ui()
        self.init_shortcuts()
        self.start_websocket()
    
    def init_shortcuts(self):
        """Initialize global shortcuts."""
        shortcut_config = self.config.get('shortcut', {'type': 'keyboard', 'value': '<ctrl>+<alt>+h'})
        self.input_manager.update_shortcut(shortcut_config)
        self.input_manager.triggered.connect(self._toggle_dashboard)
    
    def load_config(self) -> dict:
        """Load configuration from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading config: {e}")
        
        return {
            "home_assistant": {"url": "", "token": ""},
            "appearance": {"theme": "system", "rows": 2},
            "shortcut": {"type": "keyboard", "value": "<ctrl>+<alt>+h"},
            "buttons": []
        }
    
    def save_config(self):
        """Save configuration to file."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def init_theme(self):
        """Initialize theming."""
        theme = self.config.get('appearance', {}).get('theme', 'system')
        self.theme_manager.set_theme(theme)
    
    def init_ha_client(self):
        """Initialize Home Assistant client."""
        ha_config = self.config.get('home_assistant', {})
        self.ha_client.configure(
            url=ha_config.get('url', ''),
            token=ha_config.get('token', '')
        )
    
    def init_ui(self):
        """Initialize UI components."""
        # Create dashboard
        rows = self.config.get('appearance', {}).get('rows', 2)
        self.dashboard = Dashboard(config=self.config, theme_manager=self.theme_manager, rows=rows)
        self.dashboard.set_buttons(self.config.get('buttons', []), self.config.get('appearance', {}))
        
        # Connect signals
        self.dashboard.button_clicked.connect(self.on_button_clicked)
        self.dashboard.add_button_clicked.connect(self.on_edit_button_requested) # Open editor on add
        self.dashboard.edit_button_requested.connect(self.on_edit_button_requested)
        self.dashboard.clear_button_requested.connect(self.on_clear_button_requested)
        self.dashboard.buttons_reordered.connect(self.on_buttons_reordered)
        self.dashboard.climate_value_changed.connect(self.on_climate_value_changed)  # Climate control
        self.dashboard.settings_saved.connect(self._on_embedded_settings_saved)  # Embedded settings
        self.dashboard.rows_changed.connect(self.fetch_initial_states)  # Refresh states after row change
        self.dashboard.edit_button_saved.connect(self.on_edit_button_saved) # Embedded button editor
        
        # Initialize embedded SettingsWidget
        self.dashboard._init_settings_widget(self.config, self.input_manager)
        
        # Create tray manager
        self.tray_manager = TrayManager(
            on_left_click=self._toggle_dashboard,
            on_settings=self._show_settings,
            on_quit=self._quit,
            theme=self.theme_manager.get_effective_theme()
        )
        self.tray_manager.start()
        
        # Connect theme changes to tray
        self.theme_manager.theme_changed.connect(self.tray_manager.set_theme)
    
    def start_websocket(self):
        """Start a new WebSocket connection."""
        ha_config = self.config.get('home_assistant', {})
        if not ha_config.get('url') or not ha_config.get('token'):
            print("No HA config, skipping WebSocket")
            return
        
        print("Starting WebSocket connection...")
        
        # Create fresh WebSocket client
        self._ha_websocket = HAWebSocket(
            url=ha_config.get('url', ''),
            token=ha_config.get('token', '')
        )
        
        # Subscribe to configured entities
        for btn in self.config.get('buttons', []):
            entity_id = btn.get('entity_id')
            if entity_id:
                self._ha_websocket.subscribe_entity(entity_id)
        
        # Connect signals
        self._ha_websocket.state_changed.connect(self.on_state_changed)
        self._ha_websocket.notification_received.connect(self.on_notification)
        self._ha_websocket.connected.connect(self.on_ws_connected)
        self._ha_websocket.disconnected.connect(self.on_ws_disconnected)
        self._ha_websocket.error.connect(self.on_ws_error)
        
        # Create and start thread
        self._ws_thread = WebSocketThread(self._ha_websocket)
        self._ws_thread.start()
    
    def stop_websocket(self, on_finished=None):
        """Stop the WebSocket connection gracefully (async)."""
        print("Stopping WebSocket...")
        
        # IMPORTANT: Disconnect signals FIRST to prevent ghost emissions
        if self._ha_websocket:
            try:
                self._ha_websocket.state_changed.disconnect(self.on_state_changed)
                self._ha_websocket.notification_received.disconnect(self.on_notification)
                self._ha_websocket.connected.disconnect(self.on_ws_connected)
                self._ha_websocket.disconnected.disconnect(self.on_ws_disconnected)
                self._ha_websocket.error.disconnect(self.on_ws_error)
            except TypeError:
                pass
        
        # Helper to cleanup
        def delete_ws_obj():
            if self._ha_websocket:
                self._ha_websocket.deleteLater()
                self._ha_websocket = None
            if on_finished:
                on_finished()
        
        if self._ws_thread:
            # Stop is now NON-BLOCKING
            self._ws_thread.stop()
            old_thread = self._ws_thread
            self._ws_thread = None
            
            if old_thread.isRunning():
                # Connect cleanup to signal
                old_thread.finished.connect(old_thread.deleteLater)
                old_thread.finished.connect(delete_ws_obj)
            else:
                old_thread.deleteLater()
                delete_ws_obj()
        else:
            delete_ws_obj()
        
        print("WebSocket stop requested")
    
    def stop_fetch_thread(self):
        """Stop the fetch thread and wait for it to finish."""
        if self._fetch_thread:
            if self._fetch_thread.isRunning():
                self._fetch_thread.quit()
                self._fetch_thread.wait(2000)
            old_thread = self._fetch_thread
            self._fetch_thread = None
            old_thread.deleteLater()

    def stop_entity_list_thread(self):
        """Stop the entity list fetch thread."""
        if self._entity_list_thread:
            if self._entity_list_thread.isRunning():
                self._entity_list_thread.quit()
                self._entity_list_thread.wait(2000)
            self._entity_list_thread.deleteLater()
            self._entity_list_thread = None
    
    def stop_all_threads(self):
        """Stop all background threads properly."""
        print("Stopping all threads...")
        self.stop_websocket()
        self.stop_fetch_thread()
        self.stop_entity_list_thread()
        # Thread pool handles its own cleanup on exit usually, or we can clear:
        self.thread_pool.clear()
        
        print("All threads stopped")
    
    @pyqtSlot()
    def _toggle_dashboard(self):
        """Toggle dashboard visibility."""
        if self.dashboard:
            self.dashboard.toggle()
    
    @pyqtSlot()
    def _show_settings(self):
        """Show settings in dashboard."""
        if self.dashboard:
            if not self.dashboard.isVisible():
                self.dashboard.show()
                # If hidden, show_near_tray logic might be better?
                # But show() is fine.
                
            self.dashboard.show_settings()
    
    @pyqtSlot()
    def _quit(self):
        """Quit the application."""
        self.stop_all_threads()
        if self.tray_manager:
            self.tray_manager.stop()
        QApplication.instance().quit()
    
    @pyqtSlot(dict)
    def on_settings_saved(self, new_config: dict):
        """Handle settings saved."""
        print("Settings saved, reinitializing...")
        self.config = new_config
        self.save_config()
        self.stop_all_threads()
        QApplication.processEvents()
        
        self.init_theme()
        self.init_ha_client()
        
        # Update dashboard grid and rows
        if self.dashboard:
            rows = self.config.get('appearance', {}).get('rows', 2)
            self.dashboard.set_rows(rows)
            self.dashboard.set_buttons(self.config.get('buttons', []), self.config.get('appearance', {}))
        
        # Update shortcut
        shortcut_config = self.config.get('shortcut', {'type': 'keyboard', 'value': '<ctrl>+<alt>+h'})
        self.input_manager.update_shortcut(shortcut_config)
        
        self.start_websocket()
        print("Reinitialization complete")
    
    @pyqtSlot(int)
    def on_edit_button_requested(self, slot: int):
        """Handle request to edit a button at slot."""
        print(f"Edit requested for slot {slot}")
        
        # Ensure dashboard stays open or we open a modal on top?
        # Modal on top is fine.
        
        # Fetch entities if we don't have them
        if not self._available_entities:
            self.fetch_all_entities(lambda: self._open_button_editor(slot))
        else:
            self._open_button_editor(slot)

    def fetch_all_entities(self, callback):
        """Fetch all entities then call callback."""
        ha_config = self.config.get('home_assistant', {})
        url = ha_config.get('url', '')
        token = ha_config.get('token', '')
        
        if not url or not token:
            print("Cannot fetch entities: missing config")
            return
            
        print("Fetching all entities for editor...")
        self.stop_entity_list_thread()
        
        self._entity_list_thread = EntityFetchThread(url, token)
        self._entity_list_thread.finished.connect(lambda entities: self._on_entities_ready(entities, callback))
        # Handle error?
        self._entity_list_thread.start()
        
    def _on_entities_ready(self, entities: list, callback):
        """Handle entities fetched."""
        print(f"Entities fetched: {len(entities)}")
        self._available_entities = entities
        callback()
        
    def _open_button_editor(self, slot: int):
        """Open the editor for a button slot."""
        if not self.dashboard:
            return
            
        # Ensure dashboard is visible
        if not self.dashboard.isVisible():
            self.dashboard.show()
        
        # Find existing config for this slot
        buttons = self.config.get('buttons', [])
        existing_config = next((b for b in buttons if b.get('slot') == slot), None)
        
        # Show embedded editor
        self.dashboard.show_edit_button(slot, existing_config, self._available_entities)

    @pyqtSlot(dict)
    def _on_embedded_settings_saved(self, new_config: dict):
        """Handle settings saved from embedded SettingsWidget."""
        print("Embedded settings saved")
        
        # Check what changed
        old_ha_config = self.config.get('home_assistant', {})
        new_ha_config = new_config.get('home_assistant', {})
        
        ha_changed = (old_ha_config.get('url') != new_ha_config.get('url') or 
                      old_ha_config.get('token') != new_ha_config.get('token'))
        
        # Update config
        self.config = new_config
        self.save_config()
        
        # Apply row changes
        rows = self.config.get('appearance', {}).get('rows', 2)
        if self.dashboard:
            self.dashboard.set_rows(rows)
            # Re-apply buttons (appearance might have changed)
            self.dashboard.set_buttons(self.config.get('buttons', []), self.config.get('appearance', {}))
        
        # Apply shortcut changes
        if self.input_manager:
            shortcut = self.config.get('shortcut', {})
            if shortcut.get('type') and shortcut.get('value'):
                self.input_manager.update_shortcut(shortcut)
        
        # Only restart networking if HA config changed
        if ha_changed:
            print("HA config changed, restarting connections...")
            self.init_ha_client()
            
            # Restart WebSocket (connection may have changed)
            def restart():
                self.start_websocket()
                self.fetch_initial_states()
                
            self.stop_websocket(on_finished=restart)
        else:
            print("HA config unchanged, skipping connection restart")
            # Just refresh button styles/states potentially
            self.theme_manager.set_theme(self.config.get('appearance', {}).get('theme', 'system'))

    @pyqtSlot(int)
    def on_clear_button_requested(self, slot: int):
        """Clear button at slot."""
        buttons = self.config.get('buttons', [])
        new_buttons = [b for b in buttons if b.get('slot') != slot]
        
        if len(new_buttons) != len(buttons):
            self.config['buttons'] = new_buttons
            self.save_config()
            
            if self.dashboard:
                self.dashboard.set_buttons(self.config['buttons'], self.config.get('appearance', {}))
                
            # Restart WS to cleanup subscriptions
            self.stop_websocket(on_finished=self.start_websocket)

    @pyqtSlot(dict)
    def on_button_clicked(self, config: dict):
        """Handle dashboard button click."""
        btn_type = config.get('type', 'switch')
        entity_id = config.get('entity_id', '')
        
        # Handle switch, curtain, and script types
        if btn_type in ('switch', 'curtain', 'script') and entity_id:
            # Debounce check - prevent rapid clicks
            current_time = time.time()
            last_time = self._last_click_time.get(entity_id, 0)
            
            # Allow skipping debounce for sliders/dimmers
            skip_debounce = config.get('skip_debounce', False)
            
            if not skip_debounce and (current_time - last_time < self._click_cooldown):
                print(f"Debounce: ignoring rapid click for {entity_id}")
                return
            
            self._last_click_time[entity_id] = current_time
            
            # Determine service to call
            if btn_type == 'curtain':
                # Curtains use cover.toggle
                domain = 'cover'
                action = 'toggle'
            elif btn_type == 'script':
                # Scripts use script.turn_on
                domain = 'script'
                action = 'turn_on'
            else:
                # Switches use configured service
                service = config.get('service', 'homeassistant.toggle')
                domain, action = service.split('.', 1) if '.' in service else ('homeassistant', 'toggle')
            
            print(f"Calling service: {domain}.{action} for {entity_id}")
            
            ha_config = self.config.get('home_assistant', {})
            service_data = config.get('service_data')
            
            # Use Runnable and ThreadPool
            runnable = ServiceCallRunnable(
                self.ha_client,
                domain, action, entity_id,
                service_data
            )
            # You can connect signals if you need feedback:
            runnable.signals.call_complete.connect(lambda success: print(f"Service call result: {success}"))
            
            self.thread_pool.start(runnable)
    
    @pyqtSlot(str, float)
    def on_climate_value_changed(self, entity_id: str, temperature: float):
        """Handle climate temperature change from dashboard."""
        print(f"Setting climate {entity_id} to {temperature}°C")
        
        ha_config = self.config.get('home_assistant', {})
        
        runnable = ServiceCallRunnable(
            self.ha_client,
            'climate', 'set_temperature', entity_id,
            {'temperature': temperature}
        )
        runnable.signals.call_complete.connect(lambda success: print(f"Climate service call result: {success}"))
        self.thread_pool.start(runnable)
    
    def _cleanup_service_thread(self, thread):
        """No longer used with QThreadPool."""
        pass
    
    @pyqtSlot(int)
    def on_add_button_clicked(self, slot: int):
        """Handle add button click on empty slot."""
        # This is now handled by on_edit_button_requested
        # We can re-route or keep separate if needed, but logic is same
        self.on_edit_button_requested(slot)
    
    @pyqtSlot(int, int)
    def on_buttons_reordered(self, source: int, target: int):
        """Handle button reordering via drag and drop."""
        print(f"Reordering buttons: {source} -> {target}")
        buttons = self.config.get('buttons', [])
        
        # Find buttons in source and target slots list
        source_btn = next((b for b in buttons if b.get('slot') == source), None)
        target_btn = next((b for b in buttons if b.get('slot') == target), None)
        
        # Update slots logic config
        if source_btn:
            source_btn['slot'] = target
        if target_btn:
            target_btn['slot'] = source
            
        # Save and update logic
        self.save_config()
        if self.dashboard:
            self.dashboard.set_buttons(buttons)
        
        # Refresh states for new positions
        self.fetch_initial_states()



    @pyqtSlot(int)
    def on_edit_button_requested(self, slot: int):
        """Handle edit button request."""
        # Find config for this slot
        buttons = self.config.get('buttons', [])
        config = next((b for b in buttons if b.get('slot') == slot), None)
        
        # Fetch entities first
        ha_config = self.config.get('home_assistant', {})
        if not ha_config.get('url') or not ha_config.get('token'):
            # If no config, just open empty
            if self.dashboard:
                self.dashboard.show_edit_button(slot, config, [])
            return

        # Reuse Generic Entity Fetcher
        self._entity_fetcher = EntityFetchThread(
            ha_config['url'], 
            ha_config['token']
        )
        self._entity_fetcher.finished.connect(
            lambda entities: self._on_entities_ready(entities, slot, config)
        )
        self._entity_fetcher.start()

    def _on_entities_ready(self, entities, slot, config):
        if self.dashboard:
            self.dashboard.show_edit_button(slot, config, entities)
            
    @pyqtSlot(dict)
    def on_edit_button_saved(self, new_config: dict):
        """Handle button config saved from embedded editor."""
        slot = new_config.get('slot')
        
        buttons = self.config.get('buttons', [])
        # Remove old config for this slot if exists
        buttons = [b for b in buttons if b.get('slot') != slot]
        
        buttons.append(new_config)
        self.config['buttons'] = buttons
        
        self.save_config()
        if self.dashboard:
            self.dashboard.set_buttons(buttons, self.config.get('appearance', {}))
            self.fetch_initial_states() # Refresh state for new item

    @pyqtSlot(int, int)
    def on_buttons_reordered(self, source: int, target: int):
        """Handle button reordering via drag and drop."""
        print(f"Reordering buttons: {source} -> {target}")
        buttons = self.config.get('buttons', [])
        
        # Find buttons in source and target slots
        source_btn = next((b for b in buttons if b.get('slot') == source), None)
        target_btn = next((b for b in buttons if b.get('slot') == target), None)
        
        # Update slots
        if source_btn:
            source_btn['slot'] = target
        if target_btn:
            target_btn['slot'] = source
            
        # Save and update
        self.save_config()
        if self.dashboard:
            self.dashboard.set_buttons(buttons, self.config.get('appearance', {}))
        
        # Refresh states for new positions
        self.fetch_initial_states()

    @pyqtSlot(str, dict)
    def on_state_changed(self, entity_id: str, state: dict):
        """Handle entity state change from WebSocket."""
        print(f"State changed: {entity_id} -> {state.get('state', 'unknown')}")
        if self.dashboard:
            self.dashboard.update_entity_state(entity_id, state)
    
    @pyqtSlot(str, str)
    def on_notification(self, title: str, message: str):
        """Handle Home Assistant notification."""
        print(f"Notification: {title} - {message}")
        self.notification_manager.show_ha_notification(title, message)
    
    @pyqtSlot()
    def on_ws_connected(self):
        """Handle WebSocket connected."""
        print("WebSocket connected!")
        if self.tray_manager:
            self.tray_manager.update_title("Prism Desktop - Connected")
        
        # Fetch initial states
        self.fetch_initial_states()
    
    @pyqtSlot()
    def on_ws_disconnected(self):
        """Handle WebSocket disconnected."""
        print("WebSocket disconnected!")
        if self.tray_manager:
            self.tray_manager.update_title("Prism Desktop - Disconnected")
    
    @pyqtSlot(str)
    def on_ws_error(self, error: str):
        """Handle WebSocket error."""
        print(f"WebSocket error: {error}")
    
    def fetch_initial_states(self):
        """Fetch initial states for all configured entities."""
        # Stop any existing fetch thread first
        self.stop_fetch_thread()
        
        entity_ids = []
        for btn in self.config.get('buttons', []):
            entity_id = btn.get('entity_id')
            if entity_id:
                entity_ids.append(entity_id)
        
        if not entity_ids:
            return
        
        print(f"Fetching initial states for: {entity_ids}")
        
        ha_config = self.config.get('home_assistant', {})
        
        self._fetch_thread = StateFetchThread(
            self.ha_client,
            entity_ids
        )
        self._fetch_thread.state_fetched.connect(self._on_state_fetched)
        self._fetch_thread.finished.connect(self._on_fetch_finished)
        self._fetch_thread.start()
    
    @pyqtSlot(str, dict)
    def _on_state_fetched(self, entity_id: str, state: dict):
        """Handle fetched state."""
        print(f"Fetched state: {entity_id} -> {state.get('state', 'unknown')}")
        if self.dashboard:
            self.dashboard.update_entity_state(entity_id, state)
    
    @pyqtSlot()
    def _on_fetch_finished(self):
        """Handle fetch thread completion."""
        print("Initial state fetch complete")
    
    def check_first_run(self):
        """Check if this is first run and show settings if needed."""
        ha_config = self.config.get('home_assistant', {})
        if not ha_config.get('url') or not ha_config.get('token'):
            QTimer.singleShot(500, self._show_settings)

def main():
    """Application entry point."""
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Prism Desktop")
    app.setApplicationDisplayName("Prism Desktop - Home Assistant")
    
    # Load MDI icon font
    load_mdi_font()
    
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("System tray not available")
        sys.exit(1)
    
    prism = PrismDesktopApp()
    prism.check_first_run()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
