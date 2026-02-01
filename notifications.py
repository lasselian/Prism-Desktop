"""
Notifications Manager for Prism Desktop
Handles system notifications from Home Assistant.
"""

from PyQt6.QtWidgets import QSystemTrayIcon
from PyQt6.QtCore import QObject


class NotificationManager(QObject):
    """Manages system notifications."""
    
    APP_NAME = "Prism Desktop"
    
    def __init__(self, tray_icon: QSystemTrayIcon = None):
        super().__init__()
        self.tray_icon = tray_icon
    
    def set_tray_icon(self, tray_icon: QSystemTrayIcon):
        """Set the system tray icon for showing notifications."""
        self.tray_icon = tray_icon
    
    def show_ha_notification(self, title: str, message: str):
        """Show a Home Assistant notification."""
        print(f"🔔 Notification: {title} - {message}")
        
        # Try winotify first (allows custom app name)
        try:
            from winotify import Notification
            toast = Notification(
                app_id=self.APP_NAME,
                title=title,
                msg=message,
                duration="short"
            )
            toast.show()
            return
        except ImportError:
            pass
        except Exception as e:
            print(f"winotify error: {e}")
        
        # Fallback to system tray notification
        if self.tray_icon and self.tray_icon.isSystemTrayAvailable():
            self.tray_icon.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Information,
                5000
            )
    
    def show_info(self, title: str, message: str):
        """Show an info notification."""
        self.show_ha_notification(title, message)
    
    def show_error(self, title: str, message: str):
        """Show an error notification."""
        print(f"❌ Error: {title} - {message}")
        try:
            from winotify import Notification
            toast = Notification(
                app_id=self.APP_NAME,
                title=title,
                msg=message,
                duration="short"
            )
            toast.show()
        except:
            pass
