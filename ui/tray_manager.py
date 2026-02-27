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
        """Create a stylized 'Prism Desktop' isometric cube icon."""
        # Draw at a higher resolution and scale down for smooth antialiasing
        scale = 4
        canvas_size = size * scale
        image = Image.new('RGBA', (canvas_size, canvas_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Center and dimensions
        cx = canvas_size // 2
        cy = canvas_size // 2
        
        # Isometric triangle (tetrahedron from top) dimensions
        # Increased radius to make it larger
        radius = 28 * scale
        h_span = int(radius * 0.866)  # cos(30)
        v_half = int(radius * 0.5)    # sin(30)
        
        # 3 Points of the outer triangle + Center
        p_center = (cx, cy)
        p_top = (cx, cy - radius)
        p_bot_left = (cx - h_span, cy + v_half)
        p_bot_right = (cx + h_span, cy + v_half)
        
        # Colors (vibrant "Prism" palette)
        color_left = (0, 229, 255, 255)    # Cyan
        color_right = (213, 0, 249, 255)  # Magenta/Purple
        color_bottom = (41, 98, 255, 255)   # Deep Blue
        
        # Background color
        bg_color = (30, 30, 30, 255)
        
        # For light theme, darken colors slightly to ensure high contrast on white trays
        if self.theme != 'dark':
            color_left = (0, 180, 210, 255)
            color_right = (180, 0, 200, 255)
            color_bottom = (25, 60, 200, 255)
            bg_color = (255, 255, 255, 255)

        # Draw rounded background
        # Reduced padding to make the icon larger overall
        bg_pad = 1 * scale
        bg_radius = 10 * scale
        if hasattr(draw, 'rounded_rectangle'):
            draw.rounded_rectangle(
                [bg_pad, bg_pad, canvas_size - bg_pad, canvas_size - bg_pad],
                radius=bg_radius,
                fill=bg_color
            )
        else:
            draw.rectangle(
                [bg_pad, bg_pad, canvas_size - bg_pad, canvas_size - bg_pad],
                fill=bg_color
            )

        # Draw the 3 faces of the isometric triangle pyramid
        # Left Face
        draw.polygon([p_center, p_top, p_bot_left], fill=color_left)
        # Right Face
        draw.polygon([p_center, p_top, p_bot_right], fill=color_right)
        # Bottom Face
        draw.polygon([p_center, p_bot_left, p_bot_right], fill=color_bottom)
        
        # Antialiasing downscale (compatible with modern Pillow)
        resampler = getattr(Image, 'Resampling', Image).LANCZOS
        image = image.resize((size, size), resampler)
        
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
