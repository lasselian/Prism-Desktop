"""
System Tray Manager for Prism Desktop
Handles the system tray icon using pystray with proper Qt thread safety.
"""

import threading
from typing import Callable, Optional
from PIL import Image, ImageDraw
import pystray
from PyQt6.QtCore import QObject, pyqtSignal


class TraySignals(QObject):
    """Qt signals for thread-safe communication from pystray."""
    left_clicked = pyqtSignal()
    settings_clicked = pyqtSignal()
    quit_clicked = pyqtSignal()


class TrayManager:
    """Manages the system tray icon and menu."""
    
    def __init__(
        self,
        on_left_click: Optional[Callable] = None,
        on_settings: Optional[Callable] = None,
        on_quit: Optional[Callable] = None,
        theme: str = 'dark'
    ):
        self.on_left_click = on_left_click
        self.on_settings = on_settings
        self.on_quit = on_quit
        self.theme = theme
        
        self._icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None
        
        # Create Qt signals for thread-safe callbacks
        self.signals = TraySignals()
        
        # Connect signals to callbacks
        if on_left_click:
            self.signals.left_clicked.connect(on_left_click)
        if on_settings:
            self.signals.settings_clicked.connect(on_settings)
        if on_quit:
            self.signals.quit_clicked.connect(on_quit)
    
    def create_icon_image(self, size: int = 64) -> Image.Image:
        """Create a simple Home Assistant-style icon."""
        # Create a new image with transparency
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Colors based on theme
        if self.theme == 'dark':
            bg_color = (30, 30, 30, 255)
            fg_color = (0, 120, 212, 255)  # Blue accent
        else:
            bg_color = (255, 255, 255, 255)
            fg_color = (0, 120, 212, 255)
        
        # Draw circular background
        padding = 4
        draw.ellipse(
            [padding, padding, size - padding, size - padding],
            fill=bg_color,
            outline=fg_color,
            width=3
        )
        
        # Draw a simple "house" icon in the center
        center = size // 2
        house_size = size // 3
        
        # House body
        house_left = center - house_size // 2
        house_right = center + house_size // 2
        house_top = center - house_size // 4
        house_bottom = center + house_size // 2
        
        draw.rectangle(
            [house_left, house_top, house_right, house_bottom],
            fill=fg_color
        )
        
        # Roof (triangle)
        roof_peak = center - house_size // 2 - 4
        draw.polygon(
            [
                (center, roof_peak),
                (house_left - 4, house_top),
                (house_right + 4, house_top)
            ],
            fill=fg_color
        )
        
        return image
    
    def _emit_left_click(self, icon=None, item=None):
        """Emit left click signal (thread-safe)."""
        self.signals.left_clicked.emit()
    
    def _emit_settings(self, icon=None, item=None):
        """Emit settings signal (thread-safe)."""
        self.signals.settings_clicked.emit()
    
    def _emit_quit(self, icon=None, item=None):
        """Emit quit signal (thread-safe)."""
        self.signals.quit_clicked.emit()
    
    def create_menu(self) -> pystray.Menu:
        """Create the right-click context menu."""
        return pystray.Menu(
            # This is the default action (triggered by left-click/double-click)
            pystray.MenuItem(
                "Show Dashboard",
                self._emit_left_click,
                default=True  # This makes it the action for left-click
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Settings",
                self._emit_settings
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Quit",
                self._emit_quit
            )
        )
    
    def start(self):
        """Start the tray icon in a separate thread."""
        icon_image = self.create_icon_image()
        
        self._icon = pystray.Icon(
            name="Prism Desktop",
            icon=icon_image,
            title="Prism Desktop - Home Assistant",
            menu=self.create_menu()
        )
        
        # Run in separate thread
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()
    
    def stop(self):
        """Stop the tray icon."""
        if self._icon:
            self._icon.stop()
    
    def set_theme(self, theme: str):
        """Update the icon theme."""
        self.theme = theme
        if self._icon:
            self._icon.icon = self.create_icon_image()
    
    def update_title(self, title: str):
        """Update the tray icon tooltip."""
        if self._icon:
            self._icon.title = title
