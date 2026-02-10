from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import (
    Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, pyqtProperty, QRect, QPoint, QPointF, QRectF
)
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QBrush, QPen, QLinearGradient, QConicalGradient, QPainterPath
)
from ui.icons import get_icon, get_mdi_font
from core.utils import SYSTEM_FONT

class DimmerOverlay(QWidget):
    """
    Overlay slider that morphs from a button.
    """
    value_changed = pyqtSignal(int)      # 0-100
    finished = pyqtSignal()
    morph_changed = pyqtSignal(float)    # 0.0 - 1.0
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        # Raise to draw on top of other widgets
        self.raise_()
        self.hide()
        
        self._value = 0 # 0-100 brightness
        self._text = "Dimmer"
        self._color = QColor("#FFD700") # Fill color
        self._base_color = QColor("#2d2d2d") # Background color
        
        # Animation
        self._morph_progress = 0.0
        self.anim = QPropertyAnimation(self, b"morph_progress")
        self.anim.setDuration(350) 
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic) 
        self.anim.finished.connect(self.on_anim_finished)

        # Border Spin Animation (Rainbow)
        self._border_progress = 0.0
        self.anim_border = QPropertyAnimation(self, b"border_progress")
        self.anim_border.setDuration(1500)
        self.anim_border.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        self._is_closing = False
        self._border_effect = 'Rainbow'
        self._start_geom = QRect()
        self._target_geom = QRect()

    def get_morph_progress(self):
        return self._morph_progress
        
    def set_morph_progress(self, val):
        self._morph_progress = val
        self.morph_changed.emit(val)
        
        # Interpolate geometry
        current_rect = QRect(
            int(self._start_geom.x() + (self._target_geom.x() - self._start_geom.x()) * val),
            int(self._start_geom.y() + (self._target_geom.y() - self._start_geom.y()) * val),
            int(self._start_geom.width() + (self._target_geom.width() - self._start_geom.width()) * val),
            int(self._start_geom.height() + (self._target_geom.height() - self._start_geom.height()) * val)
        )
        self.setGeometry(current_rect)
        self.update()
        
    morph_progress = pyqtProperty(float, get_morph_progress, set_morph_progress)
    
    def get_border_progress(self):
        return self._border_progress
        
    def set_border_progress(self, val):
        self._border_progress = val
        self.update()
        
    border_progress = pyqtProperty(float, get_border_progress, set_border_progress)
    
    def start_morph(self, start_geo: QRect, target_geo: QRect, initial_value: int, text: str, color: QColor = None, base_color: QColor = None):
        """Start the morph animation sequence."""
        self._start_geom = start_geo
        self._target_geom = target_geo
        self._value = initial_value
        self._text = text
        self._color = color or QColor("#FFD700")
        self._base_color = base_color or QColor("#2d2d2d")
        self._is_closing = False
        
        self.setGeometry(start_geo)
        self.show()
        self.raise_()
        self.activateWindow()
        self.grabMouse() # Hijack input immediately
        
        self.anim.stop()
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()
        
        # Start border spin
        self.anim_border.stop()
        self.anim_border.setStartValue(0.0)
        self.anim_border.setEndValue(1.0)
        self.anim_border.start()

    def close_morph(self):
        """Morph back to original and close."""
        self._is_closing = True
        self.releaseMouse()
        
        self.anim.stop()
        self.anim.setStartValue(self._morph_progress)
        self.anim.setEndValue(0.0)
        self.anim.start()
        
    def on_anim_finished(self):
        if self._is_closing:
            self.hide()
            self.finished.emit()
            
    def mousePressEvent(self, event):
        """Handle click: grab mouse and update value immediately."""
        event.accept()
        # Explicitly grab mouse to track movement outside widget
        self.grabMouse()
        self.mouseMoveEvent(event)

    def mouseMoveEvent(self, event):
        """Calculate value based on X position."""
        rect = self.rect()
        if rect.width() == 0: return
        
        # Use mapFromGlobal for robust out-of-bounds tracking
        local_pos = self.mapFromGlobal(event.globalPosition().toPoint())
        x = local_pos.x()
        
        pct = x / rect.width()
        pct = max(0.0, min(1.0, pct))
        
        new_val = int(pct * 100) # HA uses 0-255 usually, but UI is 0-100 preferred
        if new_val != self._value:
            self._value = new_val
            self.update()
            self.value_changed.emit(self._value)

    def mouseReleaseEvent(self, event):
        """Commit value and close."""
        self.close_morph()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        
        # Background - Use base color to match button
        painter.setBrush(self._base_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 12, 12)
        
        if self._is_closing:
             pass
             
        # Progress Bar Fill
        # width based on value 
        fill_width = int(rect.width() * (self._value / 100.0))
        if fill_width > 0:
            fill_rect = QRect(0, 0, fill_width, rect.height())
            
            # Gradient for fill
            grad = QLinearGradient(0, 0, rect.width(), 0)
            grad.setColorAt(0, self._color.darker(120))
            grad.setColorAt(1, self._color)
            
            painter.setBrush(grad)
            
            # Clip to rounded rect
            path = QPainterPath()
            path.addRoundedRect(QRectF(rect), 12, 12)
            painter.setClipPath(path)
            
            painter.drawRect(fill_rect)
            
        # Draw Rainbow Border (Spin) if animating
        if self.anim_border.state() == QPropertyAnimation.State.Running:
            if self._border_effect == 'Rainbow':
                self._draw_rainbow_border(painter, rect)
            elif self._border_effect == 'Aurora Borealis':
                self._draw_aurora_border(painter, rect)
            
        # Text & Percent
        # Fade in text as we expand
        painter.setOpacity(1.0) # Reset opacity from border animation
        painter.setClipping(False) # Reset clip
        
        alpha = int(255 * (self._morph_progress if not self._is_closing else self._morph_progress))
        if alpha < 0: alpha = 0
        
        # Use Same Styles as DashboardButton
        painter.setPen(QColor(255, 255, 255, alpha))
        
        # Draw Label (Left)
        font_label = QFont(SYSTEM_FONT, 11, QFont.Weight.DemiBold)
        font_label.setCapitalization(QFont.Capitalization.AllUppercase)
        painter.setFont(font_label)
        
        # Adjust rect for padding
        text_rect = rect.adjusted(16, 0, -16, 0)
        painter.setPen(QColor(255, 255, 255, int(alpha * 0.7))) # Slightly dimmer label
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._text)
            
        # Draw Percent (Right)
        font_val = QFont(SYSTEM_FONT, 20, QFont.Weight.Light)
        painter.setFont(font_val)
        painter.setPen(QColor(255, 255, 255, alpha))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{self._value}%")

    def set_border_effect(self, effect: str):
        self._border_effect = effect
        self.update()

    def _draw_rainbow_border(self, painter, rect):
        colors = ["#4285F4", "#EA4335", "#FBBC05", "#34A853", "#4285F4"]
        self._draw_gradient_border(painter, rect, colors)

    def _draw_aurora_border(self, painter, rect):
        colors = ["#00C896", "#0078FF", "#8C00FF", "#0078FF", "#00C896"]
        self._draw_gradient_border(painter, rect, colors)

    def _draw_gradient_border(self, painter, rect, colors):
        angle = self._border_progress * 360.0 * 1.5
        
        opacity = 1.0
        if self._border_progress > 0.8:
            opacity = (1.0 - self._border_progress) / 0.2
        painter.setOpacity(opacity)

        gradient = QConicalGradient(QPointF(rect.center()), angle)
        for i, color in enumerate(colors):
            gradient.setColorAt(i / (len(colors) - 1), QColor(color))
        
        pen = QPen()
        pen.setWidth(2) 
        pen.setBrush(QBrush(gradient))
        
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        border_rect = QRectF(rect).adjusted(1, 1, -1, -1)
        painter.drawRoundedRect(border_rect, 12, 12)


class ClimateOverlay(QWidget):
    """
    Overlay for climate control with +/- buttons.
    Stays open until explicitly closed.
    """
    value_changed = pyqtSignal(float)     # Temperature value
    mode_changed = pyqtSignal(str)        # HVAC mode
    fan_changed = pyqtSignal(str)         # Fan mode
    finished = pyqtSignal()
    morph_changed = pyqtSignal(float)     # 0.0 - 1.0
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.raise_()
        self.hide()
        
        self._value = 20.0  # Target temperature
        self._text = "Climate"
        self._color = QColor("#EA4335")  # Default red/warm
        self._base_color = QColor("#2d2d2d")
        self._min_temp = 5.0
        self._max_temp = 35.0
        self._step = 0.5
        
        # Advanced Mode State
        self._advanced_mode = False
        self._current_hvac_mode = 'off'
        self._current_fan_mode = 'auto'
        self._hvac_modes = [] # Available modes
        self._fan_modes = []  # Available fan modes
        
        # Animation
        self._morph_progress = 0.0
        self.anim = QPropertyAnimation(self, b"morph_progress")
        self.anim.setDuration(350)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.finished.connect(self.on_anim_finished)
        
        # Border Spin Animation (Rainbow)
        self._border_progress = 0.0
        self.anim_border = QPropertyAnimation(self, b"border_progress")
        self.anim_border.setDuration(1500)
        self.anim_border.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        self._border_effect = 'Rainbow'
        
        self._is_closing = False
        self._start_geom = QRect()
        self._target_geom = QRect()
        
        # Button rects (calculated in paintEvent)
        self._btn_minus = QRect()
        self._btn_plus = QRect()
        self._btn_close = QRect()
        
        # Advanced UI Rects
        self._mode_btns = [] # list of (rect, mode_name)
        self._fan_btns = []  # list of (rect, fan_name)
    
    def get_morph_progress(self):
        return self._morph_progress
        
    def set_morph_progress(self, val):
        self._morph_progress = val
        self.morph_changed.emit(val)
        
        # Interpolate geometry
        current_rect = QRect(
            int(self._start_geom.x() + (self._target_geom.x() - self._start_geom.x()) * val),
            int(self._start_geom.y() + (self._target_geom.y() - self._start_geom.y()) * val),
            int(self._start_geom.width() + (self._target_geom.width() - self._start_geom.width()) * val),
            int(self._start_geom.height() + (self._target_geom.height() - self._start_geom.height()) * val)
        )
        self.setGeometry(current_rect)
        self.update()
        
    morph_progress = pyqtProperty(float, get_morph_progress, set_morph_progress)
    
    def get_border_progress(self):
        return self._border_progress
        
    def set_border_progress(self, val):
        self._border_progress = val
        self.update()
        
    border_progress = pyqtProperty(float, get_border_progress, set_border_progress)

    def get_content_opacity(self):
        return self._content_opacity
        
    def set_content_opacity(self, val):
        self._content_opacity = val
        self.update()
        
    content_opacity = pyqtProperty(float, get_content_opacity, set_content_opacity)
    
    def start_morph(self, start_geo: QRect, target_geo: QRect, initial_value: float, text: str, 
                   color: QColor = None, base_color: QColor = None, advanced_mode: bool = False,
                   current_state: dict = None):
        """Start the morph animation sequence."""
        self._start_geom = start_geo
        
        # If advanced mode, force target height to accommodate UI
        self._target_geom = target_geo
        self._advanced_mode = advanced_mode
        
        if advanced_mode:
            # Expand height to cover two rows (168px)
            new_h = 168 
            
            # Align top with start_geo top
            self._target_geom.setHeight(new_h)
            self._target_geom.moveTop(start_geo.top())
            
            # Check bounds
            parent_h = self.parent().height() if self.parent() else 600
            
            # If expands past bottom, align bottom (Expand Up)
            if self._target_geom.bottom() > parent_h:
                self._target_geom.moveBottom(start_geo.bottom())
                
            # If still past top
            if self._target_geom.top() < 0:
                self._target_geom.moveTop(0)
            
            # Content Fade Animation Logic
            self._content_opacity = 0.0
            self.content_anim = QPropertyAnimation(self, b"content_opacity")
            self.content_anim.setDuration(300)
            self.content_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
            self.content_anim.setStartValue(0.0)
            self.content_anim.setEndValue(1.0)
            

            
            # Parse state for current modes
            self._hvac_modes = ['off', 'heat', 'cool', 'auto'] # Default
            self._fan_modes = ['auto', 'low', 'medium', 'high'] # Default
            
            if current_state:
                self._current_hvac_mode = current_state.get('state', 'off')
                attrs = current_state.get('attributes', {})
                self._current_fan_mode = attrs.get('fan_mode', 'auto')
                if attrs.get('hvac_modes'):
                    self._hvac_modes = attrs.get('hvac_modes')
                if attrs.get('fan_modes'):
                     # Filter out 'on'/'off' if they are just on/off generic
                    self._fan_modes = attrs.get('fan_modes')
        
        self._value = initial_value
        self._text = text
        self._color = color or QColor("#EA4335")
        self._base_color = base_color or QColor("#2d2d2d")
        self._is_closing = False
        
        self.setGeometry(start_geo)
        self.show()
        self.raise_()
        self.activateWindow()
        
        self.anim.stop()
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()
        
        # Start border spin
        self.anim_border.stop()
        self.anim_border.setStartValue(0.0)
        self.anim_border.setEndValue(1.0)
        self.anim_border.start()

    def close_morph(self):
        """Morph back to original and close."""
        self._is_closing = True
        
        # Fade out content immediately
        self._content_opacity = 0.0
        self.update()
        
        self.anim.stop()
        self.anim.setStartValue(self._morph_progress)
        self.anim.setEndValue(0.0)
        self.anim.start()
        
    def on_anim_finished(self):
        if self._is_closing:
            self.hide()
            self.finished.emit()
        elif self._advanced_mode:
            # Animation finished opening in advanced mode -> Fade in content
            if hasattr(self, 'content_anim'):
                self.content_anim.start()
    
    def adjust_temp(self, delta: float):
        """Adjust temperature by delta."""
        new_val = self._value + delta
        new_val = max(self._min_temp, min(self._max_temp, new_val))
        if new_val != self._value:
            self._value = new_val
            self.update()
            self.value_changed.emit(self._value)
    
    def mousePressEvent(self, event):
        """Handle button clicks."""
        pos = event.pos()
        
        if self._btn_close.contains(pos):
            self.close_morph()
        elif self._btn_minus_click.contains(pos):
            self.adjust_temp(-self._step)
        elif self._btn_plus_click.contains(pos):
            self.adjust_temp(self._step)
            
        # Check Advanced Controls
        if self._advanced_mode:
            for rect_btn, mode in self._mode_btns:
                if rect_btn.contains(pos):
                    self._current_hvac_mode = mode
                    self.mode_changed.emit(mode)
                    self.update()
                    return
            
            for rect_btn, mode in self._fan_btns:
                if rect_btn.contains(pos):
                    self._current_fan_mode = mode
                    self.fan_changed.emit(mode)
                    self.update()
                    return
            
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        
        # Background
        painter.setBrush(self._base_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 12, 12)
        
        # Draw Rainbow Border (Spin) if animating
        # Draw Rainbow Border (Spin) if animating
        if self.anim_border.state() == QPropertyAnimation.State.Running:
            if self._border_effect == 'Rainbow':
                self._draw_rainbow_border(painter, rect)
            elif self._border_effect == 'Aurora Borealis':
                self._draw_aurora_border(painter, rect)
        
        # Reset opacity
        painter.setOpacity(1.0)
        
        # Content alpha based on morph progress
        base_alpha = int(255 * (self._morph_progress if not self._is_closing else self._morph_progress))
        
        # If advanced mode, content ignores morph progress and waits for content_opacity
        if self._advanced_mode:
             alpha = int(base_alpha * self._content_opacity)
        else:
             alpha = base_alpha
             
        if alpha < 10:
            return  # Don't draw content if too faded
        
        # === Apple-like "Control Pill" Design ===
        
        # 1. Close Button (Top Right)
        close_size = 20
        self._btn_close = QRect(rect.width() - close_size - 12, 8, close_size, close_size)
        painter.setFont(get_mdi_font(18))
        painter.setPen(QColor(255, 255, 255, int(alpha * 0.5)))
        painter.drawText(self._btn_close, Qt.AlignmentFlag.AlignCenter, get_icon('close'))
        
        # 2. Header / Title (Top Left)
        # Small, uppercase, subtle
        if self._advanced_mode:
             title_rect = QRect(20, 8, rect.width() - 80, 20)
             painter.setFont(QFont(SYSTEM_FONT, 8, QFont.Weight.Bold))
             painter.setPen(QColor(255, 255, 255, int(alpha * 0.4)))
             painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._text)
        else:
             # Standard centered title for simple mode
             painter.setFont(QFont(SYSTEM_FONT, 9, QFont.Weight.DemiBold))
             painter.setPen(QColor(255, 255, 255, int(alpha * 0.5)))
             painter.drawText(QRect(0, 14, rect.width(), 16), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self._text)

        # 3. Main Control Pill (Centered)
        # Layout:  ( - )   22.5°   ( + )
        
        center_y = 42 # Shifted up to avoid collision with Mode row (Y=78)
        if not self._advanced_mode: 
            center_y = rect.height() // 2 + 10
            
        
        btn_radius = 11 # 22x22 buttons (Was 30x30)
        spacing = 20
        
        # Temp Value
        font_val = QFont(SYSTEM_FONT, 16, QFont.Weight.Light) # Was 20.
        painter.setFont(font_val)
        fm = painter.fontMetrics()
        val_str = f"{self._value:.1f}°"
        text_w = fm.horizontalAdvance(val_str)
        text_h = fm.height()
        
        text_rect = QRect(0, 0, text_w + 10, text_h)
        text_rect.moveCenter(QPoint(rect.center().x(), center_y))
        
        painter.setPen(QColor(255, 255, 255, alpha))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, val_str)
        
        # Minus Button (Left of text)
        btn_x_minus = text_rect.left() - spacing - btn_radius
        self._btn_minus_center = QPoint(btn_x_minus, center_y)
        self._btn_minus_click = QRect(btn_x_minus - btn_radius, center_y - btn_radius, btn_radius*2, btn_radius*2)
        
        # Plus Button (Right of text)
        btn_x_plus = text_rect.right() + spacing + btn_radius
        self._btn_plus_center = QPoint(btn_x_plus, center_y)
        self._btn_plus_click = QRect(btn_x_plus - btn_radius, center_y - btn_radius, btn_radius*2, btn_radius*2)
        
        # Draw Buttons
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(get_mdi_font(12)) # Was 16
        
        
        # Minus
        # Soft background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(66, 133, 244, int(alpha * 0.8))) # Blue
        painter.drawEllipse(self._btn_minus_center, btn_radius, btn_radius)
        # Icon
        painter.setPen(QColor(255, 255, 255, alpha))
        painter.drawText(self._btn_minus_click, Qt.AlignmentFlag.AlignCenter, get_icon('minus'))
        
        # Plus
        # Soft background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(234, 67, 53, int(alpha * 0.8))) # Red
        painter.drawEllipse(self._btn_plus_center, btn_radius, btn_radius)
        # Icon
        painter.setPen(QColor(255, 255, 255, alpha))
        painter.drawText(self._btn_plus_click, Qt.AlignmentFlag.AlignCenter, get_icon('plus'))
        
        # === Advanced UI ===
        # Fade in using separate opacity
        if self._advanced_mode and self._content_opacity > 0.01:
             advanced_alpha = int(alpha * self._content_opacity)
             self._draw_advanced_controls(painter, rect, advanced_alpha)

    def _draw_advanced_controls(self, painter, rect, alpha):
        """Render HVAC Mode and Fan Speed controls."""
        self._mode_btns = []
        self._fan_btns = []
        
        # Ensure we have modes
        modes = self._hvac_modes or ['off', 'heat', 'cool']
        fan_modes = self._fan_modes or ['auto', 'low', 'high']
        
        # 1. HVAC Modes (Row 1) - Y = 65
        # Map modes to MDI icon names
        mode_icons = {
            'cool': 'snowflake',
            'heat': 'fire',
            'off': 'power',
            'auto': 'thermostat-auto', # or 'brightness-auto'
            'dry': 'water-percent',
            'fan_only': 'fan',
            'heat_cool': 'sun-snowflake-variant'
        }
        
        icon_size = 32
        spacing = 12
        spacing_sm = 8
        
        
        y_pos_1 = 78 # Was 60. Shifted down to clear the Control Pill.
        
        # Label
        painter.setFont(QFont(SYSTEM_FONT, 8, QFont.Weight.Bold))
        painter.setPen(QColor(255, 255, 255, int(alpha * 0.4)))
        painter.drawText(QRect(20, y_pos_1, 60, icon_size), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "MODE")
        
        # Icons
        start_x = 80
        # Use MDI Font
        painter.setFont(get_mdi_font(20)) # Slightly larger icon font
        
        for i, mode in enumerate(modes):
            x = start_x + (i * (icon_size + spacing_sm))
            # Don't draw if out of bounds
            if x + icon_size > rect.width(): break
            
            btn_rect = QRect(x, y_pos_1, icon_size, icon_size)
            self._mode_btns.append((btn_rect, mode))
            
            is_active = (mode == self._current_hvac_mode)
            if is_active:
                painter.setBrush(QColor(255, 255, 255, 40))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(btn_rect, 6, 6)
            
            # Get icon char
            icon_name = mode_icons.get(mode, 'help-circle-outline')
            icon_char = get_icon(icon_name)
            
            painter.setPen(QColor(255, 255, 255, alpha if is_active else int(alpha * 0.5)))
            painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, icon_char)

        # 2. Fan Modes (Row 2) - Y = 110 -> Shift to 105 or 110? With H=168: 60+32=92. 168-32-margin.
        # Temp ends at 50. Mode: 60-92. Fan: 110-142. Spacing seems ok.
        fan_map = {
            'low': '1', 'medium': '2', 'high': '3',
            'mid': '2', 'middle': '2', 'min': '1', 'max': 'Max'
        }
        
        y_pos_2 = 122 # Was 110. Shifted down to spacing from Mode row.
        
        # Label
        painter.setFont(QFont(SYSTEM_FONT, 8, QFont.Weight.Bold))
        painter.setPen(QColor(255, 255, 255, int(alpha * 0.4)))
        painter.drawText(QRect(20, y_pos_2, 60, icon_size), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "FAN")
        
        for i, mode in enumerate(fan_modes):
            x = start_x + (i * (icon_size + spacing_sm))
            if x + icon_size > rect.width(): break
            
            btn_rect = QRect(x, y_pos_2, icon_size, icon_size)
            self._fan_btns.append((btn_rect, mode))
            
            is_active = (mode == self._current_fan_mode)
            if is_active:
                painter.setBrush(QColor(255, 255, 255, 40))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(btn_rect, 6, 6)
            
            # Content: Icon (Auto) or Text (Numbers)
            mode_lower = mode.lower()
            if mode_lower == 'auto':
                 painter.setFont(get_mdi_font(20))
                 icon_char = get_icon('fan-auto')
                 painter.setPen(QColor(255, 255, 255, alpha if is_active else int(alpha * 0.5)))
                 painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, icon_char)
            else:
                 # Try to map to number, or use capitalized first letter/text
                 text = fan_map.get(mode_lower)
                 if not text:
                     # Try to see if it's already a number or specific string
                     if mode.isdigit():
                         text = mode
                     else:
                         # Fallback: Check for "speed 1" etc?
                         # Just use 1st char if not mapped? Or full text if short?
                         # User requested numbers. Let's try to infer or fallback to index?
                         # Simple map is safest. Fallback to Capitalized.
                         text = mode_lower.capitalize() if len(mode) > 3 else mode.upper()
                         
                 # Draw Text
                 painter.setFont(QFont(SYSTEM_FONT, 12, QFont.Weight.DemiBold))
                 painter.setPen(QColor(255, 255, 255, alpha if is_active else int(alpha * 0.5)))
                 painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, text)

    def set_border_effect(self, effect: str):
        self._border_effect = effect
        self.update()

    def _draw_rainbow_border(self, painter, rect):
        colors = ["#4285F4", "#EA4335", "#FBBC05", "#34A853", "#4285F4"]
        self._draw_gradient_border(painter, rect, colors)

    def _draw_aurora_border(self, painter, rect):
        colors = ["#00C896", "#0078FF", "#8C00FF", "#0078FF", "#00C896"]
        self._draw_gradient_border(painter, rect, colors)

    def _draw_gradient_border(self, painter, rect, colors):
        angle = self._border_progress * 360.0 * 1.5
        
        opacity = 1.0
        if self._border_progress > 0.8:
            opacity = (1.0 - self._border_progress) / 0.2
        painter.setOpacity(opacity)

        gradient = QConicalGradient(QPointF(rect.center()), angle)
        for i, color in enumerate(colors):
            gradient.setColorAt(i / (len(colors) - 1), QColor(color))
        
        pen = QPen()
        pen.setWidth(2) 
        pen.setBrush(QBrush(gradient))
        
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        border_rect = QRectF(rect).adjusted(1, 1, -1, -1)
        painter.drawRoundedRect(border_rect, 12, 12)
