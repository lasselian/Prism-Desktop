from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter
from ui.widgets.dashboard_button_painter import DashboardButtonPainter

class FooterButton(QPushButton):
    """
    A specialized button for the dashboard footer that inherits the 
    universal physical bevel/glass effect.
    """
    def paintEvent(self, event):
        # Draw standard QPushButton (including stylesheet backgrounds)
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Apply the shared glass edge effect
        # We use the same 0.25 intensity used for the dashboard grid
        DashboardButtonPainter.draw_button_bevel_edge(
            painter, 
            QRectF(self.rect()), 
            intensity_modifier=0.25
        )
        
        painter.end()
