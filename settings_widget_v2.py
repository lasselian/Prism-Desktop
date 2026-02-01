
"""
Rewritten Settings Widget (V2)
Clean, minimalist, and bug-free implementation of the Settings panel.
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QComboBox, QFormLayout, 
    QCheckBox, QGraphicsOpacityEffect, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtProperty, pyqtSlot, QUrl
from PyQt6.QtGui import QFont, QColor, QDesktopServices

from worker_threads import ConnectionTestThread

class SettingsWidgetV2(QWidget):
    """
    Rewritten Settings Widget.
    Uses QFormLayout for clean alignment and robust sizing.
    """
    
    settings_saved = pyqtSignal(dict)
    back_requested = pyqtSignal()
    
    def __init__(self, config: dict, theme_manager=None, input_manager=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.theme_manager = theme_manager
        self.input_manager = input_manager
        
        self._test_thread: Optional[ConnectionTestThread] = None
        self._opacity = 1.0
        self._selected_rows = config.get('appearance', {}).get('rows', 2)
        
        # Opacity effect for animations - DISABLED FOR DEBUGGING
        # self._opacity_effect = QGraphicsOpacityEffect(self)
        # self._opacity_effect.setOpacity(1.0)
        # self.setGraphicsEffect(self._opacity_effect)
        
        self.setup_ui()
        self.load_config()
        
        # Connect input manager if available
        if self.input_manager:
            self.input_manager.recorded.connect(self.on_shortcut_recorded)
        
    def get_opacity(self):
        return self._opacity
    
    def set_opacity(self, val):
        self._opacity = val
        if hasattr(self, '_opacity_effect'):
            self._opacity_effect.setOpacity(val)
        # self._opacity_effect.setOpacity(val)
        
    opacity = pyqtProperty(float, get_opacity, set_opacity)
    
    def _update_stylesheet(self):
        """Generate and apply theme-aware stylesheet."""
        if self.theme_manager:
            colors = self.theme_manager.get_colors()
        else:
            # Fallback to dark theme colors
            colors = {
                'text': '#e0e0e0',
                'window_text': '#ffffff',
                'border': '#555555',
                'base': '#2d2d2d',
                'button': '#3d3d3d',
                'button_text': '#ffffff',
                'accent': '#007aff',
            }
        
        # Determine if we're in light mode for input styling
        is_light = colors.get('text', '#ffffff') == '#1e1e1e'
        
        # Input backgrounds: slightly darker/lighter than base
        if is_light:
            input_bg = "rgba(0, 0, 0, 0.05)"
            input_border = "rgba(0, 0, 0, 0.15)"
            input_focus_bg = "rgba(0, 0, 0, 0.08)"
            checkbox_bg = "rgba(0, 0, 0, 0.05)"
            checkbox_border = "#aaa"
            section_header_color = "#666666"  # Dark gray for light mode
        else:
            input_bg = "rgba(255, 255, 255, 0.08)"
            input_border = "rgba(255, 255, 255, 0.1)"
            input_focus_bg = "rgba(255, 255, 255, 0.12)"
            checkbox_bg = "rgba(255, 255, 255, 0.05)"
            checkbox_border = "#555"
            section_header_color = "#8e8e93"  # Apple gray for dark mode
        
        self.setStyleSheet(f"""
            QWidget {{ 
                font-family: 'Segoe UI', sans-serif; 
                font-size: 13px;
                color: {colors['text']};
            }}
            QLabel#headerTitle {{
                font-size: 18px;
                font-weight: 600;
                color: {colors['window_text']};
            }}
            QLabel#sectionHeader {{
                font-size: 11px;
                font-weight: 700;
                color: {section_header_color};
                margin-top: 10px;
                margin-bottom: 2px;
            }}
            QLineEdit, QComboBox {{
                background-color: {input_bg};
                border: 1px solid {input_border};
                border-radius: 6px;
                padding: 6px 10px;
                color: {colors['text']};
                selection-background-color: {colors['accent']};
            }}
            QComboBox QAbstractItemView {{
                background-color: {colors['base']};
                border: 1px solid {colors['border']};
                color: {colors['text']};
                selection-background-color: {colors['accent']};
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 1px solid {colors['accent']};
                background-color: {input_focus_bg};
            }}
            QPushButton {{
                background-color: {colors['button']};
                color: {colors['button_text']};
                border: 1px solid {colors['border']};
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 500;
            }}
            QPushButton:hover {{ background-color: {colors['accent']}; color: white; }}
            QPushButton:pressed {{ background-color: {colors['accent']}; }}
            
            QPushButton#primaryBtn {{
                background-color: {colors['accent']};
                color: white;
                border: none;
            }}
            QPushButton#primaryBtn:hover {{ background-color: #006ce6; }}
            
            QPushButton#rowBtn {{
                min-width: 32px;
                max-width: 32px;
                min-height: 26px;
                max-height: 26px;
                border-radius: 4px;
                background-color: transparent;
                border: 1px solid {colors['border']};
                color: {colors['text']};
                font-size: 11px;
            }}
            QPushButton#rowBtn:checked {{
                background-color: {colors['accent']};
                border: 1px solid {colors['accent']};
                color: white;
            }}
            QCheckBox {{ spacing: 8px; color: {colors['text']}; }}
            QCheckBox::indicator {{
                width: 18px; height: 18px;
                border-radius: 4px;
                border: 1px solid {checkbox_border};
                background: {checkbox_bg};
            }}
            QCheckBox::indicator:checked {{
                background: {colors['accent']};
                border-color: {colors['accent']};
            }}
            
            QPushButton#recordBtn {{
                background-color: #EA4335;
                border: none;
                border-radius: 6px;
            }}
            QPushButton#recordBtn:hover {{
                background-color: #D33428;
            }}
            QPushButton#recordBtn:checked {{
                background-color: #B71C1C;
            }}
            
            QWidget#recordIcon {{
                background-color: white;
                border-radius: 6px;
            }}
            
            QPushButton#coffeeBtn {{
                background-color: {colors['accent']};
                color: white;
                border: none;
                font-weight: 500;
                font-size: 13px;
                border-radius: 6px;
                padding: 8px 16px;
            }}
            QPushButton#coffeeBtn:hover {{
                background-color: #006ce6;
            }}
        """)
        
    def setup_ui(self):
        # Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        # Apply dynamic theming
        self._update_stylesheet()
        
        # Connect theme changes for live updates
        if self.theme_manager:
            self.theme_manager.theme_changed.connect(self._update_stylesheet)
        

        
        # 1. Header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 10)
        
        self.back_btn = QPushButton("← Back")
        self.back_btn.setFixedWidth(70)
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.clicked.connect(self.back_requested.emit)
        
        title = QLabel("Settings")
        title.setObjectName("headerTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("primaryBtn")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setFixedWidth(70)
        self.save_btn.clicked.connect(self.save_settings)
        
        header_layout.addWidget(self.back_btn)
        header_layout.addWidget(title)
        header_layout.addWidget(self.save_btn)
        
        layout.addLayout(header_layout)
        
        # 2. Form Layout (Content)
        self.form = QFormLayout()
        self.form.setVerticalSpacing(14)
        self.form.setHorizontalSpacing(16)
        
        # --- Home Assistant Section ---
        self._add_section_header("HOME ASSISTANT")
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("http://homeassistant.local:8123")
        self.form.addRow("URL:", self.url_input)
        
        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setPlaceholderText("Long-Lived Access Token")
        self.form.addRow("Token:", self.token_input)
        
        # Test Connection Row
        test_row = QHBoxLayout()
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.setFixedWidth(120)
        self.test_btn.clicked.connect(self.test_connection)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #aaa;")
        
        test_row.addWidget(self.test_btn)
        test_row.addWidget(self.status_label)
        test_row.addStretch()
        self.form.addRow("", test_row)
        
        # --- Appearance Section ---
        self._add_section_header("APPEARANCE")
        
        # Theme
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["System", "Light", "Dark"])
        self.theme_combo.setFixedWidth(120)
        self.theme_combo.currentIndexChanged.connect(self.on_theme_preview)
        self.form.addRow("Theme:", self.theme_combo)

        # Border Effect
        self.border_effect_combo = QComboBox()
        self.border_effect_combo.addItems(["Rainbow", "Aurora Borealis", "None"])
        self.border_effect_combo.setFixedWidth(120)
        self.form.addRow("Border Effect:", self.border_effect_combo)
        
        # Rows (Segmented Buttons)
        rows_row = QHBoxLayout()
        rows_row.setSpacing(4)
        self.row_buttons = []
        for i in range(2, 6):  # 2, 3, 4, 5 rows
            btn = QPushButton(str(i))
            btn.setObjectName("rowBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, idx=i: self.on_row_selected(idx))
            rows_row.addWidget(btn)
            self.row_buttons.append(btn)
        rows_row.addStretch()
        self.form.addRow("Size:", rows_row)
        
        # Live Dimming
        self.live_dimming_check = QCheckBox("Enable")
        self.live_dimming_check.setChecked(True)
        self.form.addRow("Live Dimming:", self.live_dimming_check)
        
        # --- Shortcut Section ---
        self._add_section_header("SHORTCUT")
        
        shortcut_row = QHBoxLayout()
        self.shortcut_display = QLineEdit()
        self.shortcut_display.setReadOnly(True)
        self.shortcut_display.setPlaceholderText("None")
        
        self.record_btn = QPushButton()
        self.record_btn.setObjectName("recordBtn")
        self.record_btn.setCheckable(True)
        self.record_btn.setFixedSize(40, 32)
        self.record_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.record_btn.clicked.connect(self.toggle_recording)
        
        # Inner Icon Widget
        btn_layout = QHBoxLayout(self.record_btn)
        btn_layout.setContentsMargins(0,0,0,0)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.record_icon = QWidget()
        self.record_icon.setObjectName("recordIcon")
        self.record_icon.setFixedSize(12, 12)
        self.record_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) # Let clicks pass
        btn_layout.addWidget(self.record_icon)
        
        # Layout: Input (80%) - Gap - Button - Gap (10%)
        shortcut_row.addWidget(self.shortcut_display, 8)
        shortcut_row.addSpacing(12)
        shortcut_row.addWidget(self.record_btn)
        shortcut_row.addStretch(2) 
        
        self.form.addRow("Show/Hide:", shortcut_row)
        
        layout.addLayout(self.form)
        
        # --- Support Section ---
        self._add_section_header("SUPPORT")
        
        self.coffee_btn = QPushButton("Buy me a coffee ☕")
        self.coffee_btn.setObjectName("coffeeBtn")
        self.coffee_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.coffee_btn.setFixedHeight(36) # Slightly taller than standard inputs
        self.coffee_btn.clicked.connect(self.open_coffee)
        
        # Add to form layout for consistent alignment
        # Align left (stretch on right)
        coffee_row = QHBoxLayout()
        coffee_row.addWidget(self.coffee_btn)
        coffee_row.addStretch()
        
        self.form.addRow("Donate:", coffee_row)
        
        layout.addStretch() # Push everything up
        
    def _add_section_header(self, text):
        """Helper to add spaced section header."""
        lbl = QLabel(text)
        lbl.setObjectName("sectionHeader")
        self.form.addRow(lbl)

    def get_content_height(self):
        """Return suggested height."""
        # Force layout update to get accurate size
        self.adjustSize()
        return self.sizeHint().height()
        
    def load_config(self):
        """Load current config values."""
        ha = self.config.get('home_assistant', {})
        self.url_input.setText(ha.get('url', ''))
        self.token_input.setText(ha.get('token', ''))
        
        app = self.config.get('appearance', {})
        theme_map = {'system': 0, 'light': 1, 'dark': 2}
        idx = theme_map.get(app.get('theme', 'system'), 0)
        idx = theme_map.get(app.get('theme', 'system'), 0)
        self.theme_combo.setCurrentIndex(idx)
        
        effect = app.get('border_effect', 'Rainbow')
        effect_idx = self.border_effect_combo.findText(effect)
        if effect_idx >= 0:
            self.border_effect_combo.setCurrentIndex(effect_idx)
        else:
             self.border_effect_combo.setCurrentIndex(0)
        
        rows = app.get('rows', 2)
        self.on_row_selected(rows)
        
        self.live_dimming_check.setChecked(app.get('live_dimming', True))
        
        sc = self.config.get('shortcut', {})
        self.shortcut_display.setText(sc.get('value', ''))
        
    def save_settings(self):
        """Save and emit config."""
        self._cleanup_threads()
        
        # HA
        if 'home_assistant' not in self.config: self.config['home_assistant'] = {}
        self.config['home_assistant']['url'] = self.url_input.text().strip()
        self.config['home_assistant']['token'] = self.token_input.text().strip()
        
        # Appearance
        theme_map = {0: 'system', 1: 'light', 2: 'dark'}
        if 'appearance' not in self.config: self.config['appearance'] = {}
        self.config['appearance'].update({
            'theme': theme_map.get(self.theme_combo.currentIndex(), 'system'),
            'border_effect': self.border_effect_combo.currentText(),
            'rows': self._selected_rows,
            'live_dimming': self.live_dimming_check.isChecked()
        })
        
        # Shortcut handled by record signal, but good to ensure consistency
        # (Shortcut saves immediately on record in config dict)
        
        self.settings_saved.emit(self.config)

    # --- Logic ---

    def on_row_selected(self, rows):
        self._selected_rows = rows
        for i, btn in enumerate(self.row_buttons):
            btn.setChecked((i + 2) == rows)

    def on_theme_preview(self, index):
        if self.theme_manager:
            theme_map = {0: 'system', 1: 'light', 2: 'dark'}
            self.theme_manager.set_theme(theme_map.get(index, 'system'))

    def toggle_recording(self, checked):
        if not self.input_manager:
            self.record_btn.setChecked(False)
            return
            
        if checked:
            # Stop State (Square)
            self.record_icon.setStyleSheet("background-color: white; border-radius: 2px;") 
            self.shortcut_display.setText("Press keys...")
            self.input_manager.start_recording()
        else:
            # Record State (Circle)
            self.record_icon.setStyleSheet("background-color: white; border-radius: 6px;")
            self.input_manager.stop_listening()
            # Restore previous text if cancelled? 
            # Ideally input manager handles this, but for now simplistic approach:
            sc = self.config.get('shortcut', {})
            if self.shortcut_display.text() == "Press keys...":
                self.shortcut_display.setText(sc.get('value', ''))

    @pyqtSlot(dict)
    def on_shortcut_recorded(self, shortcut):
        self.record_btn.setChecked(False)
        # Reset Icon
        self.record_icon.setStyleSheet("background-color: white; border-radius: 6px;")
        self.shortcut_display.setText(shortcut.get('value', ''))
        if 'shortcut' not in self.config: self.config['shortcut'] = {}
        self.config['shortcut'] = shortcut

    def test_connection(self):
        url = self.url_input.text().strip()
        token = self.token_input.text().strip()
        
        if not url or not token:
            self.status_label.setText("⚠ Missing Info")
            return
            
        self.test_btn.setEnabled(False)
        self.status_label.setText("Testing...")
        
        if self._test_thread and self._test_thread.isRunning():
            self._test_thread.quit()
        
        self._test_thread = ConnectionTestThread(url, token)
        self._test_thread.finished.connect(self.on_test_complete)
        self._test_thread.start()

    @pyqtSlot(bool, str)
    def on_test_complete(self, success, message):
        self.test_btn.setEnabled(True)
        icon = "✅" if success else "❌"
        # Truncate long error messages
        display_msg = message[:30] + "..." if len(message) > 30 else message
        self.status_label.setText(f"{icon} {display_msg}")

    def _cleanup_threads(self):
        if self._test_thread and self._test_thread.isRunning():
            self._test_thread.quit()
            self._test_thread.wait(500)

    def open_coffee(self):
        """Open Buy Me a Coffee link."""
        QDesktopServices.openUrl(QUrl("https://www.buymeacoffee.com/lasselian"))
