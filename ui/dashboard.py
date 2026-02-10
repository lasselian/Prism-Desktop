"""
Dashboard Widget for Prism Desktop
The main popup menu with 4x2 grid of buttons/widgets.
"""

import asyncio
import time
import platform
from PyQt6.QtWidgets import (
    QWidget, QGridLayout, QPushButton, QLabel, 
    QVBoxLayout, QHBoxLayout, QFrame, QApplication, QGraphicsDropShadowEffect, QMenu,
    QGraphicsOpacityEffect, QScrollArea
)
from PyQt6.QtCore import (
    Qt, QPoint, QPointF, pyqtSignal, QPropertyAnimation, QEasingCurve, 
    QMimeData, QByteArray, QDataStream, QIODevice, pyqtProperty, QRectF, QTimer, QRect,
    pyqtSlot, QUrl, QSize

)
from PyQt6.QtGui import (
    QColor, QFont, QDrag, QPixmap, QPainter, QCursor,
    QPen, QBrush, QLinearGradient, QConicalGradient, QDesktopServices,
    QIcon

)
from ui.icons import get_icon, get_mdi_font

# Cross-platform system font
from core.utils import SYSTEM_FONT
from ui.widgets.dashboard_button import DashboardButton, MIME_TYPE
from ui.widgets.overlays import DimmerOverlay, ClimateOverlay


class FrozenScrollArea(QScrollArea):
    """ScrollArea that disables wheel scrolling."""
    def wheelEvent(self, event):
        event.accept()

class Dashboard(QWidget):
    """Main dashboard popup widget with dynamic grid."""
    
    button_clicked = pyqtSignal(dict)  # Button config
    add_button_clicked = pyqtSignal(int)  # Slot index
    buttons_reordered = pyqtSignal(int, int) # (source, target)
    edit_button_requested = pyqtSignal(int) 
    save_config_requested = pyqtSignal() # New signal to request save from parent 
    duplicate_button_requested = pyqtSignal(int)
    clear_button_requested = pyqtSignal(int)
    rows_changed = pyqtSignal()  # Emitted after row count changes and UI rebuilds
    # Signal for when settings button is clicked
    settings_clicked = pyqtSignal()
    
    def __init__(self, config: dict, theme_manager=None, input_manager=None, version: str = "Unknown", rows: int = 2, parent=None):
        super().__init__(parent)
        self.config = config
        self.theme_manager = theme_manager
        self.input_manager = input_manager
        self.version = version
        self._rows = rows
        self.buttons: list[DashboardButton] = []
        self._button_configs: list[dict] = []
        self._entity_states: dict = {} # Map entity_id -> full state dict
        
        # Entrance Animation
        self._anim_progress = 0.0
        self.anim = QPropertyAnimation(self, b"anim_progress")
        self.anim.setDuration(1500)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.anim.finished.connect(self._on_anim_finished)
        
        # Border Animation (Decoupled from entrance)
        self._border_progress = 0.0
        self.border_anim = QPropertyAnimation(self, b"glow_progress")
        self.border_anim.setDuration(1500) # Slower, elegant spin
        self.border_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        self.dimmer_overlay = DimmerOverlay(self)
        self.dimmer_overlay.value_changed.connect(self.on_dimmer_value_changed)
        self.dimmer_overlay.finished.connect(self.on_dimmer_finished)
        self.dimmer_overlay.morph_changed.connect(self.on_morph_changed)
        
        # Climate overlay
        self.climate_overlay = ClimateOverlay(self)
        self.climate_overlay.value_changed.connect(self.on_climate_value_changed)
        self.climate_overlay.mode_changed.connect(self.on_climate_mode_changed)
        self.climate_overlay.fan_changed.connect(self.on_climate_fan_changed)
        self.climate_overlay.finished.connect(self.on_climate_finished)
        self.climate_overlay.morph_changed.connect(self.on_climate_morph_changed)
        
        # Throttling
        self._last_dimmer_call = 0
        self._pending_dimmer_val = None
        self._active_dimmer_entity = None
        self.dimmer_timer = QTimer(self)
        self.dimmer_timer.setInterval(100) # 100ms throttle
        self.dimmer_timer.timeout.connect(self.process_pending_dimmer)
        
        # Climate throttling
        self._last_climate_call = 0
        self._pending_climate_val = None
        self._active_climate_entity = None
        self.climate_timer = QTimer(self)
        self.climate_timer.setInterval(500)  # 500ms throttle for climate
        self.climate_timer.timeout.connect(self.process_pending_climate)
        
        self._border_effect = 'Rainbow' # Default border effect
        
        self.setup_ui()
        
        # View switching (Grid vs Settings)
        self._current_view = 'grid'  # 'grid' or 'settings'
        self._grid_height = None  # Will be set after first show
        self._fixed_width = 428  # Fixed width to maintain
        
        
        # Height animation (Custom Timer Loop for smooth sync)
        self._anim_start_height = 0
        self._anim_target_height = 0
        self._anim_start_time = 0
        self._anim_duration = 0.25
        self._anchor_bottom_y = 0
        
        self._animation_timer = QTimer(self)
        self._animation_timer.setInterval(16) # ~60 FPS
        self._animation_timer.timeout.connect(self._on_animation_frame)
        
        # SettingsWidget (created lazily to avoid circular import at module load)
        self.settings_widget = None
        
        if self.theme_manager:
            theme_manager.theme_changed.connect(self.on_theme_changed)

        # Window Height Animation
        self._anim_height = 0
        self.height_anim = QPropertyAnimation(self, b"anim_height")
        self.height_anim.setDuration(400)
        self.height_anim.setEasingCurve(QEasingCurve.Type.OutBack) # Slight bounce
            
    def get_anim_height(self):
        return self.height()
        
    def set_anim_height(self, h):
        h = int(h)
        # Anchor to bottom if we have captured an anchor point
        if hasattr(self, '_resize_anchor_y'):
             new_y = self._resize_anchor_y - h
             self.setGeometry(self.x(), new_y, self.width(), h)
        else:
             self.setFixedSize(self.width(), h)
        
    anim_height = pyqtProperty(float, get_anim_height, set_anim_height)

    def set_rows(self, rows: int):
        """Set number of rows and rebuild grid."""
        if self._rows != rows:
            # FIX: If we're currently showing settings, defer the rebuild until
            # the hide_settings animation completes.
            if self._current_view == 'settings':
                self._pending_rows = rows
                return
            
            self._do_set_rows(rows)
    
    def handle_button_resize(self, slot_idx, span_x, span_y):
        """Handle resize request from a button."""
        
        # Validate against grid boundaries
        row = slot_idx // 4
        col = slot_idx % 4
        
        # Clamp span to available space
        max_span_x = 4 - col
        max_span_y = self._rows - row
        
        valid_span_x = min(span_x, max_span_x)
        valid_span_y = min(span_y, max_span_y)
        
        # Find config by slot field, not by array index
        config = next((c for c in self._button_configs if c.get('slot', -1) == slot_idx), None)
        if config:
            config['span_x'] = valid_span_x
            config['span_y'] = valid_span_y
        
        # Update button instance size (but DON'T rebuild grid during drag)
        for btn in self.buttons:
            if btn.slot == slot_idx:
                btn.set_spans(valid_span_x, valid_span_y)
                break

        # Live preview: rebuild grid without disrupting mouse events
        self.rebuild_grid(preview_mode=True)

    def handle_button_resize_finished(self):
        """Handle completion of resize drag."""
        # Finalize the grid (hide unused buttons, persist slots)
        self.rebuild_grid(preview_mode=False)
        self.save_config_requested.emit()

    def rebuild_grid(self, preview_mode=False):
        """Rebuild the grid using Auto-Flow algorithm."""
        # 0. Lazy Import / Init Engine
        if not hasattr(self, 'layout_engine'):
            from ui.grid_layout_engine import GridLayoutEngine
            self.layout_engine = GridLayoutEngine(cols=4)

        # 1. Clear Grid
        # In preview mode, skip hiding to preserve mouse capture if needed, 
        # but usually we need to detach from grid anyway.
        if not preview_mode:
            for btn in self.buttons:
                btn.hide()
        
        while self.grid.count():
            self.grid.takeAt(0)
            
        # 2. Calculate Layout
        # We pass self.buttons directly. The engine expects objects with .config, .slot, .span_x/y
        placements = self.layout_engine.calculate_layout(self.buttons, self._rows)
        
        max_row = 0
        
        # 3. Apply Placements
        for btn, r, c, span_y, span_x in placements:
            btn.setVisible(True)
            
            # Reset resize styling if not resizing
            if not getattr(btn, '_is_resizing', False):
                btn.resize_handle_opacity = 0.0 # Use property directly
                if hasattr(btn, 'resize_anim'):
                    btn.resize_anim.stop()
            
            # Add to grid
            self.grid.addWidget(btn, r, c, span_y, span_x)
            
            # Update button state
            new_slot = r * 4 + c
            btn.slot = new_slot
            
            # Update Config (only if not previewing drag)
            if not preview_mode and btn.config:
                btn.config['slot'] = new_slot
                
            max_row = max(max_row, r + span_y)
            
        # 4. Hide unused buttons (shouldn't be any if engine logic is correct and we passed all buttons)
        # The engine filters out buttons that don't fit? 
        # Actually our engine includes empty buttons to fill holes.
        # Any button NOT in placements should be hidden.
        placed_buttons = set(p[0] for p in placements)
        for btn in self.buttons:
            if btn not in placed_buttons:
                btn.setVisible(False)
        
        # 5. Update Height
        grid_h = (self._rows * 80) + ((self._rows - 1) * 8)
        extras = 78
        new_height = grid_h + extras
        
        start_h = self.height()
        if start_h != new_height and self._current_view == 'grid':
            if preview_mode:
                self.setFixedSize(self.width(), new_height)
                if hasattr(self, '_resize_anchor_y'):
                    new_y = self._resize_anchor_y - new_height
                    self.move(self.x(), new_y)
            else:
                self._resize_anchor_y = self.y() + self.height()
                self.height_anim.stop()
                self.height_anim.setStartValue(float(start_h))
                self.height_anim.setEndValue(float(new_height))
                self.height_anim.start()

    def get_first_empty_slot(self, span_x: int = 1, span_y: int = 1) -> int:
        """Find the first visual slot index that is completely empty and fits the span."""
        if not hasattr(self, 'layout_engine'):
            from ui.grid_layout_engine import GridLayoutEngine
            self.layout_engine = GridLayoutEngine(cols=4)
            
        return self.layout_engine.find_first_empty_slot(self.buttons, self._rows, span_x, span_y)
            
    def _do_set_rows(self, rows: int):
        """Update grid rows dynamically."""
        self._rows = rows
        
        # Update button count to match N*4 slots (classic logic)
        # This keeps the "Add" buttons available filling the space.
        current_slots = len(self.buttons)
        target_slots = rows * 4
        
        if target_slots > current_slots:
             for i in range(current_slots, target_slots):
                button = DashboardButton(slot=i, theme_manager=self.theme_manager)
                button.clicked.connect(lambda cfg, btn=button: self._on_button_clicked(btn.slot, cfg))
                button.dropped.connect(self.on_button_dropped)
                button.edit_requested.connect(self.edit_button_requested)
                button.duplicate_requested.connect(self.duplicate_button_requested)
                button.clear_requested.connect(self.clear_button_requested)
                button.dimmer_requested.connect(self.start_dimmer)
                button.climate_requested.connect(self.start_climate)
                button.resize_requested.connect(self.handle_button_resize)
                self.buttons.append(button)
                
                # Sync config list
                if i >= len(self._button_configs):
                    self._button_configs.append({})
                    
        elif target_slots < current_slots:
             for i in range(current_slots - 1, target_slots - 1, -1):
                btn = self.buttons.pop()
                btn.setParent(None)
                btn.deleteLater()
                # DON'T delete configs - they should persist so expanding rows restores them
        
        # Re-apply configs to all buttons (important when expanding rows)
        for i, button in enumerate(self.buttons):
            config = next(
                (c for c in self._button_configs if c.get('slot', -1) == i),
                {}
            )
            button.config = config
            # Apply span and update visual size
            button.set_spans(config.get('span_x', 1), config.get('span_y', 1))
            button.update_content()
            button.update_style()
            button.set_border_effect(self._border_effect)
                    
        # Now layout everything
        self.rebuild_grid()
        self.update_style()
        
        # Store grid height
        grid_h = (self._rows * 80) + ((self._rows - 1) * 8)
        extras = 78
        self._grid_height = grid_h + extras
        
        self.rows_changed.emit()
    
    def setup_ui(self):
        """Setup the dashboard UI."""
        # Reset layout if exists (not clean, but works for refresh)
        if self.layout():
             QWidget().setLayout(self.layout())

        # Frameless window
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Clear existing buttons
        self.buttons.clear()
        
        # Container
        existing_container = self.findChild(QFrame, "dashboardContainer")
        if existing_container:
            existing_container.deleteLater()
            
        self.container = QFrame(self)
        self.container.setObjectName("dashboardContainer")
        
        # Root layout for Window
        if not self.layout():
            root_layout = QVBoxLayout(self)
            root_layout.setContentsMargins(10, 10, 10, 10)
        else:
            root_layout = self.layout()
            while root_layout.count():
                child = root_layout.takeAt(0)
                if child.widget(): child.widget().deleteLater()
        
        root_layout.addWidget(self.container)
        
        # Container Layout (Stack + Footer)
        content_layout = QVBoxLayout(self.container)
        content_layout.setSpacing(0)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Stacked Widget for switching views (Grid / Settings)
        from PyQt6.QtWidgets import QStackedWidget
        self.stack_widget = QStackedWidget()
        content_layout.addWidget(self.stack_widget)
        
        # 1. Main Grid
        self.grid_widget = QWidget()
        self.grid = QGridLayout(self.grid_widget)
        self.grid.setSpacing(8)
        self.grid.setContentsMargins(12, 12, 12, 8)
        
        # FIX: Wrap Grid in ScrollArea for smooth animation
        self.grid_scroll = FrozenScrollArea()
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.grid_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.grid_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.grid_scroll.setStyleSheet("background: transparent;")
        self.grid_scroll.setWidget(self.grid_widget)
        
        self.stack_widget.addWidget(self.grid_scroll)
        
        # Create grid buttons
        total_slots = self._rows * 4
        for i in range(total_slots):
            row = i // 4
            col = i % 4
            button = DashboardButton(slot=i, theme_manager=self.theme_manager)
            button.clicked.connect(lambda cfg, btn=button: self._on_button_clicked(btn.slot, cfg))
            button.dropped.connect(self.on_button_dropped)
            button.edit_requested.connect(self.edit_button_requested)
            button.clear_requested.connect(self.clear_button_requested)
            button.dimmer_requested.connect(self.start_dimmer)
            button.climate_requested.connect(self.start_climate)
            self.grid.addWidget(button, row, col)
            self.buttons.append(button)
            
        # 2. Footer
        self.footer_widget = QWidget()
        
        # Note: Footer fade-in animation logic is handled dynamically in 
        # _fade_in_footer() to avoid "wrapped C/C++ object deleted" crashes.
        
        footer_layout = QHBoxLayout(self.footer_widget)
        footer_layout.setSpacing(8)
        footer_layout.setContentsMargins(12, 0, 12, 12)
        
        # Calc standard button width (approx)
        # Layout: 428 total width. Container inner: 408.
        # Grid margins: 12 left, 12 right -> 384 for buttons.
        # 4 buttons + 3 spaces (8px) -> 384 - 24 = 360. 360/4 = 90px per button.
        # Footer buttons: 2 buttons. Width should cover 2 grid buttons + spacing.
        # Width = 90 + 8 + 90 = 188px.
        # Height = 1/3 of 80px = ~26px.
        
        btn_width = 188
        btn_height = 26
        
        # Left Button (Home Assistant)
        self.btn_left = QPushButton("  HOME ASSISTANT") # Add space for spacing
        self.btn_left.setFixedSize(btn_width, btn_height)
        self.btn_left.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_left.clicked.connect(self.open_ha)
        
        # Create Custom HA Icon
        # Official Blue: #41bdf5
        # White Glyph
        ha_icon_char = get_icon("home-assistant")
        ha_pixmap = QPixmap(32, 32)
        ha_pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(ha_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 1. Blue Rounded Rect
        painter.setBrush(QColor("#41BDF5"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, 32, 32, 6, 6) # 6px radius for 32px is nice
        
        # 2. White Glyph
        painter.setFont(get_mdi_font(20))
        painter.setPen(QColor("white"))
        painter.drawText(ha_pixmap.rect(), Qt.AlignmentFlag.AlignCenter, ha_icon_char)
        painter.end()
        
        self.btn_left.setIcon(QIcon(ha_pixmap))
        self.btn_left.setIconSize(QSize(15, 15)) # Slightly smaller than button height (26)
        
        self.btn_left.setStyleSheet("background: rgba(255,255,255,0.1); border: none; border-radius: 4px; color: #888;")
        footer_layout.addWidget(self.btn_left)
        
        # Right Button (Settings) - now calls show_settings directly
        self.btn_settings = QPushButton("SETTINGS")
        self.btn_settings.setFixedSize(btn_width, btn_height)
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.clicked.connect(self.show_settings)
        # Style handled in update_style or inline for now
        self.btn_settings.setStyleSheet("background: rgba(255,255,255,0.1); border: none; border-radius: 4px; color: #888;")
        footer_layout.addWidget(self.btn_settings)
        
        content_layout.addWidget(self.footer_widget)
        
        # FIX: Force visibility and repaint on startup/rebuild
        self.footer_widget.show()
        self.repaint()
        QTimer.singleShot(50, self.update)
        
        # Shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)
        
        self.update_style()
        
        # Size Calculation
        width = 428
        # Height: Grid rows*80 + (rows-1)*8 + Grid top(12) + Grid bot(8) + Footer(26) + Footer bot(12) + Root margins(20)
        # = (rows*80) + (rows-1)*8 + 12 + 8 + 26 + 12 + 20
        # = (rows*80) + (rows*8) - 8 + 78
        grid_h = (self._rows * 80) + ((self._rows - 1) * 8)
        extras = 12 + 8 + 26 + 12 + 20   # 78
        height = grid_h + extras
        self.setFixedSize(width, height)
    def open_ha(self):
        """Open Home Assistant in default browser."""
        ha_cfg = self.config.get('home_assistant', {})
        url = ha_cfg.get('url', '').strip()
        if url:
             QDesktopServices.openUrl(QUrl(url))
             self.hide()

    def update_style(self):
        """Update dashboard style based on theme."""
        if self.theme_manager:
            colors = self.theme_manager.get_colors()
        else:
            colors = {
                'window': '#1e1e1e',
                'border': '#555555',
            }
        
        self.container.setStyleSheet(f"""
            QFrame#dashboardContainer {{
                background-color: {colors['window']};
                border: 1px solid {colors['border']};
                border-radius: 12px;
            }}
            QMenu {{
                background-color: #2b2b2b;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                background: transparent;
                padding: 6px 24px 6px 12px;
                color: #e0e0e0;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: #007aff;
                color: white;
            }}
        """)
        
        for button in self.buttons:
            button.update_style()
            
        # Style Footer Buttons
        if hasattr(self, 'btn_left'):
            # Use safe defaults if keys missing
            bg = colors.get('alternate_base', '#353535')
            text = colors.get('text', '#aaaaaa')
            accent = colors.get('accent', '#4285F4')
            
            btn_style = f"""
                QPushButton {{
                    background-color: {bg};
                    border: none;
                    border-radius: 4px;
                    color: {text};
                    font-family: "{SYSTEM_FONT}";
                    font-size: 11px;
                    font-weight: 600;
                    text-transform: uppercase;
                }}
                QPushButton:hover {{
                    background-color: {accent};
                    color: white;
                }}
            """
            self.btn_left.setStyleSheet(btn_style)
            self.btn_settings.setStyleSheet(btn_style)

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        # print(f"DEBUG: KeyPress {event.key()} Mods: {event.modifiers()}")
        
        # 1. Custom Shortcuts (Highest Priority)
        for button in self.buttons:
            sc = button.config.get('custom_shortcut', {})
            if sc.get('enabled') and sc.get('value'):
                if self.matches_pynput_shortcut(event, sc.get('value')):
                    # print(f"DEBUG: Triggering custom shortcut match for button {button.slot}")
                    button.simulate_click()
                    event.accept()
                    return

        # 2. Global Shortcuts (Modifier + Number)
        # Check modifier
        modifier_map = {
            'Alt': Qt.KeyboardModifier.AltModifier,
            'Ctrl': Qt.KeyboardModifier.ControlModifier,
            'Shift': Qt.KeyboardModifier.ShiftModifier
        }
        
        shortcut_config = self.config.get('shortcut', {}) if self.config else {}
        target_mod_str = shortcut_config.get('modifier', 'Alt')
        
        should_process = False
        if target_mod_str == 'None':
             # Only process if NO modifiers are pressed to perfectly match 'None'
             if event.modifiers() == Qt.KeyboardModifier.NoModifier:
                 should_process = True
        else:
            target_mod = modifier_map.get(target_mod_str)
            # Strict match? Or just "contains"?
            # User wants "Alt+1". If I press "Ctrl+Alt+1", shoud it work? 
            # Usually strict is better to avoid conflict with complex global shortcuts.
            # But the original code was: (event.modifiers() & target_mod)
            # This allows extra modifiers.
            if target_mod and (event.modifiers() & target_mod):
                should_process = True
        
        if should_process:
            key = event.key()
            if Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
                slot = key - Qt.Key.Key_1
                if 0 <= slot < len(self.buttons):
                    # Check if this button has custom shortcut enabled
                    # If so, GLOBAL shortcut should be ignored for THIS button
                    btn = self.buttons[slot]
                    sc = btn.config.get('custom_shortcut', {})
                    if sc.get('enabled'):
                        # print(f"DEBUG: Ignoring global shortcut for button {slot} due to custom override")
                        pass 
                    else:
                        btn.simulate_click()
                        event.accept()
                        return

        super().keyPressEvent(event)
        
    def matches_pynput_shortcut(self, event, shortcut_str: str) -> bool:
        """Check if QKeyEvent matches pynput shortcut string."""
        if not shortcut_str: return False
        
        parts = shortcut_str.split('+')
        
        # Check modifiers
        has_ctrl = '<ctrl>' in parts
        has_alt = '<alt>' in parts
        has_shift = '<shift>' in parts
        # has_cmd/win ignored for simplicity or added if needed
        
        modifiers = event.modifiers()
        
        if has_ctrl != bool(modifiers & Qt.KeyboardModifier.ControlModifier): return False
        if has_alt != bool(modifiers & Qt.KeyboardModifier.AltModifier): return False
        if has_shift != bool(modifiers & Qt.KeyboardModifier.ShiftModifier): return False
        
        # Check key
        # Extract the non-modifier part
        target_key = None
        for p in parts:
            if p not in ['<ctrl>', '<alt>', '<shift>', '<cmd>']:
                target_key = p
                break
        
        if not target_key: return False # Modifier only?
        
        # Normalize target_key (pynput format) vs event
        # pynput: 'a', '1', '<esc>', '<space>', '<f1>'
        
        # Handle special keys
        key = event.key()
        text = event.text().lower()
        
        # 1. Single character match (letters, numbers)
        if len(target_key) == 1:
            # Prefer text() match for characters to handle layouts, 
            # BUT text() might be empty if modifiers are held (e.g. Ctrl+A might give \x01)
            # So fallback to Key code mapping if needed.
            
            # Simple check:
            if text and text == target_key: return True
            
            # Fallback: Check key code for letters/digits if text is control char
            if key >= 32 and key <= 126: # Ascii range roughly
                try:
                    # Qt Key to char
                    if chr(key).lower() == target_key: return True
                except: pass
                
            return False

        # 2. Special keys (<esc>, <f1>, etc)
        # Strip <>
        if target_key.startswith('<') and target_key.endswith('>'):
            clean_key = target_key[1:-1].lower()
            
            # Map common keys
            map_special = {
                'esc': Qt.Key.Key_Escape,
                'space': Qt.Key.Key_Space,
                'enter': Qt.Key.Key_Return,
                'backspace': Qt.Key.Key_Backspace,
                'tab': Qt.Key.Key_Tab,
                'up': Qt.Key.Key_Up,
                'down': Qt.Key.Key_Down,
                'left': Qt.Key.Key_Left,
                'right': Qt.Key.Key_Right,
                'f1': Qt.Key.Key_F1, 'f2': Qt.Key.Key_F2, 'f3': Qt.Key.Key_F3, 'f4': Qt.Key.Key_F4,
                'f5': Qt.Key.Key_F5, 'f6': Qt.Key.Key_F6, 'f7': Qt.Key.Key_F7, 'f8': Qt.Key.Key_F8,
                'f9': Qt.Key.Key_F9, 'f10': Qt.Key.Key_F10, 'f11': Qt.Key.Key_F11, 'f12': Qt.Key.Key_F12,
                'delete': Qt.Key.Key_Delete,
                'home': Qt.Key.Key_Home,
                'end': Qt.Key.Key_End,
                'page_up': Qt.Key.Key_PageUp,
                'page_down': Qt.Key.Key_PageDown
            }
            
            if map_special.get(clean_key) == key:
                return True
                
        return False
    
    def set_buttons(self, configs: list[dict], appearance_config: dict = None):
        """Set button configurations."""
        self._button_configs = configs
        if appearance_config:
            self._live_dimming = True
            self._border_effect = appearance_config.get('border_effect', 'Rainbow')
        
        for i, button in enumerate(self.buttons):
            config = next(
                (c for c in configs if c.get('slot', -1) == i),
                None
            )
            
            # Reset state if entity changed
            new_entity = config.get('entity_id') if config else None
            old_entity = button.config.get('entity_id')
            if new_entity != old_entity:
                button._state = "off"
                button._value = ""
            
            button.config = config or {}
            # Button's slot stays as its array index (i), not config's slot
            # Apply span dimensions from config
            button.set_spans(
                button.config.get('span_x', 1),
                button.config.get('span_y', 1)
            )
            button.update_content()
            button.update_style()
            # Propagate effect
            button.set_border_effect(self._border_effect)
            
            # ENSURE connection (fix for missing signal)
            try:
                button.resize_requested.disconnect(self.handle_button_resize)
            except TypeError:
                pass # Not connected
            button.resize_requested.connect(self.handle_button_resize)
            
            try:
                button.resize_finished.disconnect(self.handle_button_resize_finished)
            except TypeError:
                pass
            button.resize_finished.connect(self.handle_button_resize_finished)
            
            try:
                button.duplicate_requested.disconnect(self.duplicate_button_requested)
            except TypeError:
                pass
            button.duplicate_requested.connect(self.duplicate_button_requested)
        
        # Rebuild grid to properly layout spanned buttons
        self.rebuild_grid()


    # (Duplicate methods removed)


    def set_effect(self, effect_name: str):
        """Set the active border effect."""
        self._effect = effect_name
        self.update()

    def paintEvent(self, event):
        """Paint overlay and effects."""
        # Only draw if animating and effect is active
        # Use border_anim state to control drawing duration
        if self.border_anim.state() == QPropertyAnimation.State.Running:
            if self._border_effect == 'Rainbow':
                self._draw_rainbow_border()
            elif self._border_effect == 'Aurora Borealis':
                self._draw_aurora_border()

    def _draw_aurora_border(self):
        """Draw the Aurora Borealis border effect."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Angle (Slower spin for aurora?)
        angle = self._border_progress * 360.0 * 1.0 
        
        # Fade out
        opacity = 1.0
        if self._border_progress > 0.8:
            opacity = (1.0 - self._border_progress) / 0.2
        painter.setOpacity(opacity)
        
        rect = QRectF(self.container.geometry()).adjusted(0, 0, 0, 0)
        
        # Aurora Colors: Green -> Blue -> Purple -> Blue -> Green
        colors = ["#00C896", "#0078FF", "#8C00FF", "#0078FF", "#00C896"]
        
        gradient = QConicalGradient(rect.center(), angle)
        for i, color in enumerate(colors):
            gradient.setColorAt(i / (len(colors) - 1), QColor(color))
        
        pen = QPen()
        pen.setWidth(3)
        pen.setBrush(QBrush(gradient))
        
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        painter.drawRoundedRect(rect, 12, 12)

    def _draw_rainbow_border(self):
        """Draw the rainbow border effect."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Angle
        angle = self._border_progress * 360.0 * 1.5
        
        # Fade out
        opacity = 1.0
        if self._border_progress > 0.8:
            opacity = (1.0 - self._border_progress) / 0.2
        painter.setOpacity(opacity)
        
        # Use container geometry to ensure tight fit
        rect = QRectF(self.container.geometry()).adjusted(0, 0, 0, 0)
        
        # Colors - Google Brand Colors
        colors = ["#4285F4", "#EA4335", "#FBBC05", "#34A853", "#4285F4"]
        
        gradient = QConicalGradient(rect.center(), angle)
        for i, color in enumerate(colors):
            gradient.setColorAt(i / (len(colors) - 1), QColor(color))
        
        pen = QPen()
        pen.setWidth(3)
        pen.setBrush(QBrush(gradient))
        
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        painter.drawRoundedRect(rect, 12, 12)
            
    def start_dimmer(self, slot: int, global_rect: QRect):
        """Start the dimmer morph sequence."""
        # Find config
        config = next((c for c in self._button_configs if c.get('slot') == slot), None)
        if not config: return
        
        entity_id = config.get('entity_id')
        if not entity_id: return
        
        self._active_dimmer_entity = entity_id
        self._active_dimmer_type = config.get('type', 'switch')  # Track type for service call
        
        # Get start value based on state
        source_btn = next((b for b in self.buttons if b.slot == slot), None)
        current_val = 0
        
        # Look up full state for attributes
        state_obj = self._entity_states.get(entity_id, {})
        attrs = state_obj.get('attributes', {})
        
        if self._active_dimmer_type == 'curtain':
            # Check for specific position attribute
            pos = attrs.get('current_position')
            if pos is not None:
                current_val = int(pos)
            elif source_btn:
                # Fallback to binary state
                current_val = 100 if source_btn._state == "open" else 0
        else:
            # Check for brightness (0-255)
            bri = attrs.get('brightness')
            if bri is not None:
                current_val = int((bri / 255.0) * 100)
            elif source_btn:
                # Fallback to binary state
                current_val = 100 if source_btn._state == "on" else 0
        
        # Colors - always use dark base for overlay visibility
        base_color = QColor("#2d2d2d")
        
        # Use button's custom color if set, otherwise theme accent
        button_color = config.get('color')
        accent_color = QColor(button_color) if button_color else QColor("#FFD700")
        
        if self.theme_manager and not button_color:
            cols = self.theme_manager.get_colors()
            accent_color = QColor(cols.get('accent', '#FFD700'))
            
        # Calculate geometries
        start_rect = self.mapFromGlobal(global_rect.topLeft())
        start_rect = QRect(start_rect, global_rect.size())
        
        # Target: Full row width starting from container's grid area
        # Use source button's actual position for target rect calculation
        # Use mapTo(self, QPoint(0,0)) for robust coordinate conversion
        src_pos = source_btn.mapTo(self, QPoint(0, 0))
        
        # Identify siblings for fading - use visual row based on Y position
        self._dimmer_siblings = []
        self._dimmer_source_btn = None  # Track source button separately
        
        # Find all buttons in the same visual row (by Y position overlap)
        src_top = src_pos.y()
        src_bottom = src_pos.y() + source_btn.height()
        
        row_buttons = []
        for btn in self.buttons:
            btn_pos = btn.mapTo(self, QPoint(0, 0))
            btn_top = btn_pos.y()
            btn_bottom = btn_pos.y() + btn.height()
            # Check if this button overlaps vertically with source
            if btn_top < src_bottom and btn_bottom > src_top:
                row_buttons.append((btn, btn_pos))
        
        # Calculate target_rect from actual row button positions
        if row_buttons:
            # Find leftmost and rightmost buttons
            row_buttons.sort(key=lambda x: x[1].x())
            first_btn, first_pos = row_buttons[0]
            last_btn, last_pos = row_buttons[-1]
            
            # Target spans from first button to end of last button
            target_x = first_pos.x()
            target_width = (last_pos.x() + last_btn.width()) - first_pos.x()
            
            # Use source button height for uniform overlay height? 
            # Or max height of row? 
            # Climate uses source_btn.height(). Dimmer usually replaces the row.
            # If we have mixed heights, using source_btn.height() aligns with the clicked element.
            target_rect = QRect(target_x, src_pos.y(), target_width, source_btn.height())
            
            # Sibling fading setup
            for btn, _ in row_buttons:
                if btn.slot != slot:
                    self._dimmer_siblings.append(btn)
                else:
                    self._dimmer_source_btn = btn  # Store source
                    btn.set_faded(0.0)  # Hide source button immediately
        else:
            # Fallback
            target_rect = QRect(src_pos, source_btn.size())
            
        # Start!
        self.dimmer_overlay.set_border_effect(self._border_effect)
        self.dimmer_overlay.start_morph(
            start_rect, 
            target_rect, 
            current_val, 
            config.get('label', 'Dimmer'),
            color=accent_color,
            base_color=base_color
        )
        
        self.dimmer_timer.start()

    def on_morph_changed(self, progress: float):
        """Update sibling opacity during morph."""
        opacity = 1.0 - progress
        for btn in getattr(self, '_dimmer_siblings', []):
            btn.set_faded(opacity)

    def on_dimmer_value_changed(self, value):
        """Queue dimming request."""
        self._pending_dimmer_val = value

    def on_dimmer_finished(self):
        """Cleanup after dimmer closes."""
        self.dimmer_timer.stop()
        
        # For curtains, send the final position only on release
        dimmer_type = getattr(self, '_active_dimmer_type', 'switch')
        final_val = getattr(self, '_final_dimmer_val', None)
        
        if dimmer_type == 'curtain' and final_val is not None and self._active_dimmer_entity:
            # Send final curtain position
            self.button_clicked.emit({
                "service": "cover.set_cover_position",
                "entity_id": self._active_dimmer_entity,
                "service_data": {"position": final_val}
            })
        
        elif dimmer_type != 'curtain' and final_val is not None and self._active_dimmer_entity:
            # Send final brightness for lights (ensures update if live dimming was off)
            self.button_clicked.emit({
                "service": "light.turn_on",
                "entity_id": self._active_dimmer_entity,
                "service_data": {"brightness_pct": final_val},
                "skip_debounce": True
            })
        
        self._active_dimmer_entity = None
        self._active_dimmer_type = None
        self._pending_dimmer_val = None
        self._final_dimmer_val = None
        
        # Reset siblings
        for btn in getattr(self, '_dimmer_siblings', []):
            btn.set_faded(1.0)
        
        # Restore source button
        if getattr(self, '_dimmer_source_btn', None):
            self._dimmer_source_btn.set_faded(1.0)
            self._dimmer_source_btn = None
             
        self._dimmer_siblings = []
        self.activateWindow() # Reclaim focus

    def process_pending_dimmer(self):
        """Throttled service call."""
        if self._pending_dimmer_val is None or not self._active_dimmer_entity:
            return
            
        val = self._pending_dimmer_val
        self._pending_dimmer_val = None # Clear pending
        
        # Call appropriate service based on entity type
        dimmer_type = getattr(self, '_active_dimmer_type', 'switch')
        
        # Always store the latest value as the potential final value
        self._final_dimmer_val = val
        
        if dimmer_type == 'curtain':
            # Curtains: Only store value, send on release (in on_dimmer_finished)
            return
        
        # Check live dimming setting (only applies to lights)
        if not getattr(self, '_live_dimming', True):
            return

        # Lights use light.turn_on with brightness
        self.button_clicked.emit({
            "service": "light.turn_on",
            "entity_id": self._active_dimmer_entity,
            "service_data": {"brightness_pct": val},
            "skip_debounce": True
        })

    # ============ CLIMATE CONTROL ============
    
    climate_value_changed = pyqtSignal(str, float)  # (entity_id, temperature)
    
    def start_climate(self, slot: int, global_rect: QRect):
        """Start the climate morph sequence."""
        # Find config
        config = next((c for c in self._button_configs if c.get('slot') == slot), None)
        if not config: return
        
        entity_id = config.get('entity_id')
        if not entity_id: return
        
        self._active_climate_entity = entity_id
        
        # Get current target temp from button value or default
        source_btn = next((b for b in self.buttons if b.slot == slot), None)
        current_val = 20.0  # Default
        if source_btn and source_btn._value:
            try:
                # Parse temperature from value string like "20.5°C"
                temp_str = source_btn._value.replace('°C', '').replace('°', '').strip()
                current_val = float(temp_str)
            except:
                pass
        
        # Colors - always use dark base for overlay visibility
        base_color = QColor("#2d2d2d")
        button_color = config.get('color')
        accent_color = QColor(button_color) if button_color else QColor("#EA4335")
        
        if self.theme_manager and not button_color:
            cols = self.theme_manager.get_colors()
            accent_color = QColor(cols.get('accent', '#EA4335'))
            
        # Calculate geometries using source button's actual position
        start_rect = self.mapFromGlobal(global_rect.topLeft())
        start_rect = QRect(start_rect, global_rect.size())
        
        # Get source button's actual grid position 
        source_btn = next((b for b in self.buttons if b.slot == slot), None)
        if not source_btn:
            return
            
        # Use source button's actual position for target rect calculation
        # Use mapTo(self, QPoint(0,0)) for robust coordinate conversion
        src_pos = source_btn.mapTo(self, QPoint(0, 0))
        
        # Target: Full row width starting from container's grid area
        # Get the grid area by finding leftmost button position
        
        # Identify siblings for fading - use visual row based on Y position
        self._climate_siblings = []
        self._climate_source_btn = None  # Track source button separately
        
        # Find all buttons in the same visual row (by Y position overlap)
        src_top = src_pos.y()
        src_bottom = src_pos.y() + source_btn.height()
        
        row_buttons = []
        row_buttons = []
        for btn in self.buttons:
            # Check if this button overlaps vertically with source
            btn_pos = btn.mapTo(self, QPoint(0, 0))
            btn_top = btn_pos.y()
            btn_bottom = btn_pos.y() + btn.height()
            # Check if this button overlaps vertically with source
            if btn_top < src_bottom and btn_bottom > src_top:
                row_buttons.append((btn, btn_pos))
        
        # Calculate target_rect from actual row button positions
        if row_buttons:
            # Find leftmost and rightmost buttons
            row_buttons.sort(key=lambda x: x[1].x())
            first_btn, first_pos = row_buttons[0]
            last_btn, last_pos = row_buttons[-1]
            
            # Target spans from first button to end of last button
            target_x = first_pos.x()
            target_width = (last_pos.x() + last_btn.width()) - first_pos.x()
            target_rect = QRect(target_x, src_pos.y(), target_width, source_btn.height())
        else:
            # Fallback to source button rect
            target_rect = QRect(src_pos, source_btn.size())
        
        # Sibling fading setup (EXCLUDE source button)
        advanced_mode = config.get('advanced_mode', False)
        
        for btn, btn_pos in row_buttons:
            if btn.slot != slot:
                self._climate_siblings.append(btn)
            else:
                self._climate_source_btn = btn  # Store source
                btn.set_faded(0.0)  # Hide source button immediately
        
        # TODO: Handle advanced_mode expansion to adjacent rows if needed
        
        # Start!
        self.climate_overlay.set_border_effect(self._border_effect)
        
        # Lookup full state for advanced controls
        state_obj = self._entity_states.get(entity_id, {})
        
        self.climate_overlay.start_morph(
            start_rect, 
            target_rect, 
            current_val, 
            config.get('label', 'Climate'),
            color=accent_color,
            base_color=base_color,
            advanced_mode=config.get('advanced_mode', False),
            current_state=state_obj
        )
        
        self.climate_timer.start()

    def on_climate_morph_changed(self, progress: float):
        """Update sibling opacity during morph."""
        opacity = 1.0 - progress
        for btn in getattr(self, '_climate_siblings', []):
            btn.set_faded(opacity)

    def on_climate_value_changed(self, value: float):
        """Queue climate temperature request."""
        self._pending_climate_val = value

    def on_climate_mode_changed(self, mode: str):
        """Handle HVAC mode change (immediate)."""
        if not self._active_climate_entity: return
        
        self.button_clicked.emit({
            "service": "climate.set_hvac_mode",
            "entity_id": self._active_climate_entity,
            "service_data": {"hvac_mode": mode}
        })
        
    def on_climate_fan_changed(self, mode: str):
        """Handle Fan mode change (immediate)."""
        if not self._active_climate_entity: return
        
        self.button_clicked.emit({
            "service": "climate.set_fan_mode",
            "entity_id": self._active_climate_entity,
            "service_data": {"fan_mode": mode}
        })

    def on_climate_finished(self):
        """Cleanup after climate closes."""
        self.climate_timer.stop()
        self._active_climate_entity = None
        self._pending_climate_val = None
        
        # Reset siblings
        for btn in getattr(self, '_climate_siblings', []):
             btn.set_faded(1.0)
        
        # Restore source button
        if getattr(self, '_climate_source_btn', None):
            self._climate_source_btn.set_faded(1.0)
            self._climate_source_btn = None
             
        self._climate_siblings = []
        self.activateWindow()

    def process_pending_climate(self):
        """Throttled climate service call."""
        if self._pending_climate_val is None or not self._active_climate_entity:
            return
            
        val = self._pending_climate_val
        self._pending_climate_val = None
        
        # Emit signal for main.py to handle
        self.climate_value_changed.emit(self._active_climate_entity, val)

    def update_entity_state(self, entity_id: str, state: dict):
        """Update a button/widget when entity state changes."""
        self._entity_states[entity_id] = state
        
        for button in self.buttons:
            if button.config.get('entity_id') == entity_id:
                btn_type = button.config.get('type', 'switch')
                
                if btn_type == 'widget':
                    # Update sensor value
                    value = state.get('state', '--')
                    unit = state.get('attributes', {}).get('unit_of_measurement', '')
                    button.set_value(f"{value}{unit}")
                elif btn_type == 'climate':
                    # Update climate target temperature
                    attrs = state.get('attributes', {})
                    temp = attrs.get('temperature', '--')
                    if temp != '--':
                        button.set_value(f"{temp}°C")
                    else:
                        button.set_value("--°C")
                    # Also update state for styling
                    hvac_action = state.get('state', 'off')
                    button.set_state('on' if hvac_action not in ['off', 'unavailable'] else 'off')
                elif btn_type == 'curtain':
                    # Update curtain state (open/closed/opening/closing)
                    cover_state = state.get('state', 'closed')
                    # "open" when cover is up/open, anything else is closed
                    button.set_state('open' if cover_state == 'open' else 'closed')
                elif btn_type == 'weather':
                    # Update weather state - pass full object for attributes
                    button.set_weather_state(state)
                else:
                    # Update switch state
                    button.set_state(state.get('state', 'off'))
    
    def update_camera_image(self, entity_id: str, pixmap):
        """Update a camera button with a new image."""
        for button in self.buttons:
            if button.config.get('entity_id') == entity_id and button.config.get('type') == 'camera':
                button.set_camera_image(pixmap)
    
    def _on_button_clicked(self, slot: int, config: dict):
        """Handle button click."""
        if not config:
            self.add_button_clicked.emit(slot)
        else:
            self.button_clicked.emit(config)

    def on_button_dropped(self, source: int, target: int):
        self.buttons_reordered.emit(source, target)
    
    def on_theme_changed(self, theme: str):
        self.update_style()
    
    def show_near_tray(self):
        """Position and show the dashboard near the system tray."""
        screen = QApplication.primaryScreen()
        if not screen:
            self.show()
            return
        
        screen_rect = screen.availableGeometry()
        
        # Calculate target position but don't move there yet
        target_x = screen_rect.right() - self.width() - 10
        target_y = screen_rect.bottom() - self.height() - 10
        
        self._target_pos = QPoint(target_x, target_y)
        
        # Ensure we are visible before animating
        super().show()
        self.activateWindow()
        
        # Start Entrance Animation
        self.anim.stop()
        self.anim.setDuration(250) # Fast, snappy
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()
        
        # Start Border Animation (Independent)
        self.border_anim.stop()
        self.border_anim.setStartValue(0.0)
        self.border_anim.setEndValue(1.0)
        self.border_anim.start()
    
    def toggle(self):
        if self.isVisible() and self.windowOpacity() > 0.1:
            self.close_animated()
        else:
            self.show_near_tray()
    
    def close_animated(self):
        """Fade out and slide down, then hide."""
        self.anim.stop()
        self.border_anim.stop() # Stop the glow too
        
        # Recalculate target position from current window position
        self._target_pos = QPoint(self.x(), self.y())
        
        self.anim.setDuration(200)
        self.anim.setEasingCurve(QEasingCurve.Type.InQuad)
        self.anim.setStartValue(self._anim_progress)
        self.anim.setEndValue(0.0)
        self.anim.start()
        
    def _on_anim_finished(self):
        """Handle animation completion (hide if closing)."""
        # Robust check for near-zero
        if self._anim_progress < 0.01:
            super().hide()

    def focusOutEvent(self, event):
        # We rely on changeEvent for robust window-level focus loss
        # but focusOutEvent is still good for some edge cases
        super().focusOutEvent(event)
    
    def changeEvent(self, event):
        """Handle window activation changes."""
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow():
                # Window lost focus? Close it.
                # Use small delay to allow for things like dialogs or transient windows
                QTimer.singleShot(100, self._check_hide)
        super().changeEvent(event)
    
    def _check_hide(self):
        # If we are not the active window, close.
        if not self.isActiveWindow():
            self.close_animated()
            
    def get_anim_progress(self):
        return self._anim_progress
        
    def set_anim_progress(self, val):
        self._anim_progress = val
        
        # 1. Opacity
        self.setWindowOpacity(val)
        
        # 2. Slide Up (Entrance) / Slide Down (Exit)
        # Offset: 0 at 1.0 (open), +20 at 0.0 (closed)
        if hasattr(self, '_target_pos'):
            offset = int((1.0 - val) * 20)
            self.move(self._target_pos.x(), self._target_pos.y() + offset)
            
        self.update() # Trigger repaint for border effects
        
    anim_progress = pyqtProperty(float, get_anim_progress, set_anim_progress)

    def get_glow_progress(self):
        return self._border_progress
        
    @pyqtSlot(float)
    def set_glow_progress(self, val):
        self._border_progress = val
        self.update() 
        
    glow_progress = pyqtProperty(float, get_glow_progress, set_glow_progress)

    def showEvent(self, event):
        """Standard show event."""
        super().showEvent(event)
        # We handle animation in show_near_tray usually, but for safety:
        self.activateWindow()
        self.setFocus()
    
    # ============ VIEW SWITCHING (Grid <-> Settings) ============
    
    def _init_settings_widget(self, config: dict, input_manager=None):
        """Initialize the SettingsWidget (call from main.py after Dashboard creation)."""
        # Store for re-initialization after set_rows() rebuilds UI
        self._settings_config = config
        self._settings_input_manager = input_manager
        
        # IMPORT Settings Widget
        from ui.settings_widget import SettingsWidget
        
        self.settings_widget = SettingsWidget(config, self.theme_manager, input_manager, self.version, self)
        self.settings_widget.back_requested.connect(self.hide_settings)
        self.settings_widget.settings_saved.connect(self._on_settings_saved)
        
        # Wrap in ScrollArea for smooth animation (avoids squashing)
        self.settings_scroll = QScrollArea()
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.settings_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.settings_scroll.setFrameShape(QFrame.Shape.NoFrame)
        # Transparent background
        self.settings_scroll.setStyleSheet("background: transparent;")
        # Disable wheel scrolling - content should fit
        self.settings_scroll.wheelEvent = lambda e: e.ignore()
        self.settings_scroll.setWidget(self.settings_widget)
        
        # Add ScrollArea to stack (index 1)
        self.stack_widget.addWidget(self.settings_scroll)
        # Ensure grid SCROLL is visible
        self.stack_widget.setCurrentWidget(self.grid_scroll)
        
        # Clear cached height so it re-calculates with new settings widget
        self._cached_settings_height = None

        # Init Button Editor (Embedded)
        try:
            from ui.button_edit_widget import ButtonEditWidget
            # Create a placeholder instance to be ready
            self.edit_widget = ButtonEditWidget([], theme_manager=self.theme_manager, input_manager=self.input_manager, parent=self)
            self.edit_widget.saved.connect(self._on_edit_saved)
            self.edit_widget.cancelled.connect(self._on_edit_cancelled)
            
            self.edit_scroll = QScrollArea()
            self.edit_scroll.setWidget(self.edit_widget)
            self.edit_scroll.setWidgetResizable(True)
            self.edit_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.edit_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.edit_scroll.setStyleSheet("background: transparent; border: none;")
            self.edit_scroll.setFrameShape(QFrame.Shape.NoFrame)
            # Disable wheel scrolling - content should fit
            self.edit_scroll.wheelEvent = lambda e: e.ignore()
            
            self.stack_widget.addWidget(self.edit_scroll)
        except ImportError:
            print("Could not import ButtonEditWidget")

    def _on_settings_saved(self, config: dict):
        """Handle settings saved - emit signal and return to grid."""
        if self.settings_widget:
            self.settings_widget.set_opacity(1.0) # Reset in case
            
        # Update local config immediately for visual feedback
        app = config.get('appearance', {})
        self._border_effect = app.get('border_effect', 'Rainbow')
        self._live_dimming = True
        
        # Propagate to buttons
        for btn in self.buttons:
            btn.set_border_effect(self._border_effect)
        
        self.settings_saved.emit(config)
        self.hide_settings()
            
    def _on_edit_saved(self, config: dict):
        """Handle save from embedded editor."""
        # Find existing button config to update or append?
        # The main app handles actual saving, we just bubble up
        # BUT we need to close the view
        self.transition_to('grid')
        self.edit_button_saved.emit(config)
        
    def _on_edit_cancelled(self):
        self.transition_to('grid')
        
    edit_button_saved = pyqtSignal(dict) # Signals back to main
    
    def show_edit_button(self, slot: int, config: dict = None, entities: list = None):
        """Open the embedded button editor."""
        if self._current_view == 'edit_button': return
        
        # Update the widget content
        self.edit_widget.slot = slot
        self.edit_widget.config = config or {}
        self.edit_widget.entities = entities or []
        # IMPORTANT: Populate entities FIRST, then load config so entity_id can be selected
        self.edit_widget.populate_entities()
        self.edit_widget.load_config()
        
        # Transition
        self.transition_to('edit_button')

    settings_saved = pyqtSignal(dict)
    
    def _calculate_view_height(self, view_name: str) -> int:
        """Calculate target height for a given view."""
        if view_name == 'grid':
            # Use current height if available, or calculate from rows
            if self._grid_height:
                return self._grid_height
            # Fallback
            return (self._rows * 80) + ((self._rows - 1) * 8)
            
        elif view_name == 'settings':
            # Calculate dynamic settings height
            if self.settings_widget:
                # Always recalculate for accurate sizing
                content_h = self.settings_widget.get_content_height()
                settings_height = content_h + 30  # Small padding for container margins
                
                # Clamp against screen height
                screen = QApplication.primaryScreen()
                if screen:
                    max_h = screen.availableGeometry().height() * 0.9
                    settings_height = max(300, min(settings_height, int(max_h)))
                else:
                    settings_height = max(300, min(settings_height, 800))
                    
                return settings_height
            return 450
            
        elif view_name == 'edit_button':
            # Calculate dynamic editor height
            if hasattr(self, 'edit_widget'):
                content_h = self.edit_widget.get_content_height()
                # Add small padding for container margins
                h = content_h + 30
                return max(300, min(h, 600))
            return 400
            
        # Default fallback for unknown views
        return 400

    def _lock_view_sizes(self, target_view: str, target_height: int):
        """Lock widget sizes before animation to prevent jitter."""
        width = self.container.width() if self.container.width() > 0 else (self._fixed_width - 20)
        
        if target_view == 'settings':
            if self.settings_widget:
                self.settings_widget.setFixedSize(width, target_height)
        
        elif target_view == 'edit_button':
            if hasattr(self, 'edit_widget'):
                self.edit_widget.setFixedSize(width, target_height)
                
        elif target_view == 'grid':
            # Lock Grid Widget size to true grid height
            true_grid_h = getattr(self, '_captured_grid_widget_h', None)
            if not true_grid_h:
                true_grid_h = (self._rows * 80) + ((self._rows - 1) * 8)
            self.grid_widget.setFixedSize(width, true_grid_h)

    def transition_to(self, view_name: str):
        """
        Generic method to transition between views with smooth animation.
        view_name: 'grid', 'settings', 'edit_button', etc.
        """
        if self._current_view == view_name:
            return

        # 1. Capture state before transition
        if self._current_view == 'grid':
            self._grid_height = self.height()
            self._captured_grid_widget_h = self.grid_widget.height()
            
        # 2. Update view state
        self._current_view = view_name
        
        # 3. Calculate heights
        start_height = self.height()
        target_height = self._calculate_view_height(view_name)
        
        # 4. Prepare Animation
        self._anim_start_height = start_height
        self._anim_target_height = target_height
        self._anim_start_time = time.perf_counter()
        self._anim_duration = 0.25
        self._anchor_bottom_y = self.geometry().y() + self.height()
        
        # 5. Handle Footer Visibility
        if view_name == 'grid':
            # Footer will be shown/faded-in after animation in _on_transition_done
            pass
        else:
            self.footer_widget.hide()
            
        # 6. Button Opacity (if leaving grid)
        if view_name != 'grid':
             # Optional: fade out buttons
             pass 
        else:
            # Returning to grid: restore opacity
            for btn in self.buttons:
                btn.set_faded(1.0)

        # 7. Unlock Window Constraints
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)
        
        # 8. Switch Stack & Lock Content
        self._lock_view_sizes(view_name, target_height)
        
        if view_name == 'settings':
            self.stack_widget.setCurrentWidget(self.settings_scroll)
        elif view_name == 'grid':
            self.stack_widget.setCurrentWidget(self.grid_scroll)
        elif view_name == 'edit_button':
            if hasattr(self, 'edit_scroll'):
                self.stack_widget.setCurrentWidget(self.edit_scroll)
            
        # 9. Start Animation
        self._animation_timer.start()

    def show_settings(self):
        """Morph from Grid view to Settings view."""
        self.transition_to('settings')
    
    def hide_settings(self):
        """Morph from Settings view back to Grid view."""
        self.transition_to('grid')

    def _on_animation_frame(self):
        """Custom high-precision animation loop."""
        now = time.perf_counter()
        elapsed = now - self._anim_start_time
        progress = min(1.0, elapsed / self._anim_duration)
        
        # Cubic Ease Out: 1 - pow(1 - x, 3)
        t = 1.0 - pow(1.0 - progress, 3)
        
        # Calculate current height
        current_h = int(self._anim_start_height + (self._anim_target_height - self._anim_start_height) * t)
        
        # Update Geometry
        # Anchor to bottom: new_y = bottom - new_height
        new_y = self._anchor_bottom_y - current_h
        current_x = self.x()
        
        # Single atomic update
        self.setGeometry(current_x, new_y, self._fixed_width, current_h)
        
        if progress >= 1.0:
            self._animation_timer.stop()
            if self._current_view == 'grid':
                # Special handling for returning to grid
                pass
            
            self._on_transition_done()

    def _fade_in_footer(self):
        """Fade in footer with dynamic effect creation to prevent crashes."""
        from PyQt6.QtWidgets import QGraphicsOpacityEffect
        
        # Create FRESH effect and animation each time
        effect = QGraphicsOpacityEffect(self.footer_widget)
        effect.setOpacity(0.0)
        self.footer_widget.setGraphicsEffect(effect)
        
        # Store refs to prevent garbage collection during anim
        self._current_footer_effect = effect
        self._current_footer_anim = QPropertyAnimation(effect, b"opacity")
        self._current_footer_anim.setDuration(300)
        self._current_footer_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._current_footer_anim.setStartValue(0.0)
        self._current_footer_anim.setEndValue(1.0)
        
        # Cleanup on finish
        self._current_footer_anim.finished.connect(self._on_footer_fade_finished)
        
        self.footer_widget.show()
        self._current_footer_anim.start()

    def _on_footer_fade_finished(self):
        """Remove opacity effect after fade-in to save resources/prevent bugs."""
        self.footer_widget.setGraphicsEffect(None)
        # Clear references
        self._current_footer_effect = None
        self._current_footer_anim = None
    
    def _on_transition_done(self):
        """After transition (morph), restore styles and cleanup."""
        try:
            # Not actually using QPropertyAnimation for window, so this might be old code
            # But just in case
            if hasattr(self, 'height_anim') and self.height_anim:
                 self.height_anim.finished.disconnect(self._on_transition_done)
        except:
            pass
            
        # Unlock grid size so it behaves normally (if we are in grid view)
        if self._current_view == 'grid':
            self.grid_widget.setMinimumSize(0, 0)
            self.grid_widget.setMaximumSize(16777215, 16777215)
        
            # FIX: Process pending row change if any (deferred from set_rows)
            pending = getattr(self, '_pending_rows', None)
            if pending is not None:
                self._pending_rows = None
                self._do_set_rows(pending)
                # Show footer after rebuild (with fade-in)
                self._fade_in_footer()
                
                # After rebuild, reposition
                self._reposition_after_morph()
                return
        
        # Re-lock the window to its final size
        # Use target height from animation vars or calculate fresh
        t_height = self._grid_height if self._current_view == 'grid' else self._anim_target_height
        
        # Safety fallback
        if not t_height: t_height = self.height()
            
        self.setFixedSize(self._fixed_width, int(t_height))
        
        # Show footer now that animation is complete (with fade-in) -- ONLY IF GRID
        if self._current_view == 'grid':
            self._fade_in_footer()
        
        # Reposition window to bottom-right corner
        self._reposition_after_morph()
    
    def _reposition_after_morph(self):
        """Reposition window to keep it anchored to bottom-right."""
        screen = QApplication.primaryScreen()
        if not screen:
            return
        screen_rect = screen.availableGeometry()
        x = screen_rect.right() - self.width() - 10
        y = screen_rect.bottom() - self.height() - 10
        self.move(x, y)

