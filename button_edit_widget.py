
"""
Embedded Button Editor Widget
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QComboBox, QFormLayout,
    QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QFont

class ButtonEditWidget(QWidget):
    """
    Widget for editing button configuration directly in the dashboard.
    Matches SettingsWidgetV2 style.
    """
    
    saved = pyqtSignal(dict)
    cancelled = pyqtSignal()
    
    def __init__(self, entities: list, config: dict = None, slot: int = 0, theme_manager=None, parent=None):
        super().__init__(parent)
        self.entities = entities or []
        self.config = config or {}
        self.slot = slot
        self.theme_manager = theme_manager
        
        self.setup_ui()
        self.load_config()
    
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
            color_btn_border = "#333"
            section_header_color = "#666666"  # Dark gray for light mode
        else:
            input_bg = "rgba(255, 255, 255, 0.08)"
            input_border = "rgba(255, 255, 255, 0.1)"
            input_focus_bg = "rgba(255, 255, 255, 0.12)"
            color_btn_border = "white"
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
            
            QPushButton#colorBtn {{
                border-radius: 4px;
                border: 2px solid transparent;
            }}
            QPushButton#colorBtn:checked {{
                border: 2px solid {color_btn_border};
            }}
        """)
        
    def setup_ui(self):
        # Apply dynamic theming
        self._update_stylesheet()
        
        # Connect theme changes for live updates
        if self.theme_manager:
            self.theme_manager.theme_changed.connect(self._update_stylesheet)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        
        # 1. Header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 10)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedWidth(70)
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.cancelled.emit)
        
        title_text = "Edit Button" if self.config else "Add Button"
        title = QLabel(title_text)
        title.setObjectName("headerTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("primaryBtn")
        self.save_btn.setFixedWidth(70)
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.clicked.connect(self.save)
        
        header_layout.addWidget(self.cancel_btn)
        header_layout.addWidget(title)
        header_layout.addWidget(self.save_btn)
        
        layout.addLayout(header_layout)
        
        # 2. Form
        self.form = QFormLayout()
        self.form.setVerticalSpacing(14)
        self.form.setHorizontalSpacing(16)
        
        # --- Config Section ---
        self._add_section_header("CONFIGURATION")
        
        self.label_input = QLineEdit()
        self.label_input.setPlaceholderText("e.g. Living Room")
        self.form.addRow("Label:", self.label_input)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Switch", "Sensor Widget", "Climate", "Curtain", "Script"])
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        self.form.addRow("Type:", self.type_combo)
        
        self.entity_combo = QComboBox()
        self.entity_combo.setEditable(True)
        self.entity_combo.setMaxVisibleItems(15)
        self.entity_combo.lineEdit().setPlaceholderText("Select or type entity ID...")
        self.entity_combo.lineEdit().setPlaceholderText("Select or type entity ID...")
        self.populate_entities()
        self.form.addRow("Entity:", self.entity_combo)
        
        # Advanced Mode (Climate Only)
        self.advanced_mode_check = QCheckBox("Advanced Mode")
        self.advanced_mode_check.setToolTip("Enable fan and mode controls")
        self.advanced_mode_check.setVisible(False)
        self.form.addRow("", self.advanced_mode_check)
        
        # Service (Switches only)
        self.service_label = QLabel("Service:")
        self.service_combo = QComboBox()
        self.service_combo.addItems(["toggle", "turn_on", "turn_off"])
        self.form.addRow(self.service_label, self.service_combo)
        
        # --- Appearance Section ---
        # --- Appearance Section ---
        self._add_section_header("APPEARANCE")
        
        # Icon Input
        self.icon_input = QLineEdit()
        self.icon_input.setPlaceholderText("e.g. mdi:lightbulb")
        self.form.addRow("Icon:", self.icon_input)
        
        # Color Picker
        color_widget = QWidget()
        color_layout = QHBoxLayout(color_widget)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.setSpacing(8)
        
        self.preset_colors = [
            ("#4285F4", "Blue"),
            ("#34A853", "Green"),
            ("#EA4335", "Red"),
            ("#9C27B0", "Purple"),
            ("#E91E63", "Pink"),
            ("#607D8B", "Gray"),
        ]
        
        self.color_buttons = []
        self.selected_color = "#4285F4"
        
        for color_hex, tooltip in self.preset_colors:
            btn = QPushButton()
            btn.setObjectName("colorBtn")
            btn.setFixedSize(24, 24)
            btn.setCheckable(True)
            btn.setToolTip(tooltip)
            btn.setStyleSheet(f"background-color: {color_hex};")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, c=color_hex: self.select_color(c))
            color_layout.addWidget(btn)
            self.color_buttons.append((btn, color_hex))
            
        color_layout.addStretch()
        self.form.addRow("Color:", color_widget)
        
        layout.addLayout(self.form)

    def _add_section_header(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("sectionHeader")
        self.form.addRow(lbl)

    def populate_entities(self):
        """Populate entity dropdown filtered by selected type."""
        # Save current selection to restore if possible
        current_entity = self.entity_combo.currentText()
        
        self.entity_combo.clear()
        if not self.entities: return
        
        # Determine allowed domains based on selected type
        type_idx = self.type_combo.currentIndex()
        if type_idx == 0:  # Switch
            allowed_domains = {'light', 'switch', 'input_boolean'}
        elif type_idx == 1:  # Sensor Widget
            allowed_domains = {'sensor', 'binary_sensor'}
        elif type_idx == 2:  # Climate
            allowed_domains = {'climate'}
        elif type_idx == 3:  # Curtain
            allowed_domains = {'cover'}
        elif type_idx == 4:  # Script
            allowed_domains = {'script'}
        else:
            allowed_domains = None  # Show all
        
        # Group by domain (filtered)
        domains = {}
        for entity in self.entities:
            eid = entity.get('entity_id', '')
            domain = eid.split('.')[0] if '.' in eid else 'other'
            
            # Filter by allowed domains
            if allowed_domains and domain not in allowed_domains:
                continue
                
            friendly = entity.get('attributes', {}).get('friendly_name', eid)
            
            if domain not in domains: domains[domain] = []
            domains[domain].append((eid, friendly))
            
        for domain in sorted(domains.keys()):
            for eid, friendly in sorted(domains[domain], key=lambda x: x[0]):
                 self.entity_combo.addItem(eid, friendly)
                 self.entity_combo.setItemData(self.entity_combo.count()-1, friendly, Qt.ItemDataRole.ToolTipRole)
        
        # Try to restore previous selection
        if current_entity:
            idx = self.entity_combo.findText(current_entity)
            if idx >= 0:
                self.entity_combo.setCurrentIndex(idx)

    def on_type_changed(self, index):
        is_switch = (index == 0)
        is_climate = (index == 2)
        
        self.service_label.setVisible(is_switch)
        self.service_combo.setVisible(is_switch)
        self.advanced_mode_check.setVisible(is_climate)
        
        # Refresh entity list for the new type
        self.populate_entities()
        
    def select_color(self, color_hex):
        self.selected_color = color_hex
        for btn, c in self.color_buttons:
            btn.setChecked(c == color_hex)
            
    def load_config(self):
        if not self.config:
            self.select_color("#4285F4")
            self.entity_combo.setCurrentIndex(-1)
            self.entity_combo.setCurrentText("")
            self.label_input.clear()
            self.icon_input.clear()
            self.type_combo.setCurrentIndex(0)
            self.service_combo.setCurrentIndex(0)
            return
            
        self.label_input.setText(self.config.get('label', ''))
        self.icon_input.setText(self.config.get('icon', ''))
        
        types = {'switch': 0, 'widget': 1, 'climate': 2, 'curtain': 3, 'script': 4}
        self.type_combo.setCurrentIndex(types.get(self.config.get('type'), 0))
        
        eid = self.config.get('entity_id', '')
        if eid:
            self.entity_combo.setCurrentText(eid)
            # Try to match in combo
            idx = self.entity_combo.findText(eid)
            if idx >= 0: self.entity_combo.setCurrentIndex(idx)
            
        service = self.config.get('service', 'toggle')
        svc_name = service.split('.')[-1]
        svc_idx = self.service_combo.findText(svc_name)
        if svc_idx >= 0: self.service_combo.setCurrentIndex(svc_idx)
        
        self.advanced_mode_check.setChecked(self.config.get('advanced_mode', False))
        
        self.select_color(self.config.get('color', '#4285F4'))
        
    def get_content_height(self):
        # Force layout update to get accurate size after content changes
        self.adjustSize()
        return self.sizeHint().height()

    def save(self):
        entity_id = self.entity_combo.currentText().strip()
        type_idx = self.type_combo.currentIndex()
        
        btn_type = 'switch'
        if type_idx == 1: btn_type = 'widget'
        elif type_idx == 2: btn_type = 'climate'
        elif type_idx == 3: btn_type = 'curtain'
        elif type_idx == 4: btn_type = 'script'
        
        domain = entity_id.split('.')[0] if '.' in entity_id else 'homeassistant'
        svc_action = self.service_combo.currentText()
        
        new_config = {
            'slot': self.slot,
            'label': self.label_input.text().strip() or entity_id,
            'type': btn_type,
            'entity_id': entity_id,
            'color': self.selected_color,
            'icon': self.icon_input.text().strip()
        }
        
        if btn_type == 'switch':
            new_config['service'] = f"{domain}.{svc_action}"
        elif btn_type == 'climate':
            new_config['advanced_mode'] = self.advanced_mode_check.isChecked()
            
        self.saved.emit(new_config)
