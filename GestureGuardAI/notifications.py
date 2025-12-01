import threading
import time
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Callable
import logging
from datetime import datetime, timedelta
import json
import os

class NotificationManager:
    """Real-time notification system for GestureGuardAI"""

    def __init__(self, config=None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # Notification callbacks
        self.notification_callbacks: List[Callable] = []

        # Notification history
        self.notification_history = []

        # Rate limiting
        self.last_notification_time = {}
        self.min_notification_interval = timedelta(seconds=5)

        # Sound system
        self.sound_enabled = self.config.get('enable_sound_alerts', True)
        self.sound_volume = self.config.get('sound_volume', 50)

        # Email system
        self.email_enabled = self.config.get('enable_email_notifications', False)
        self.email_config = self.config.get('email', {})

        # Push notification system
        self.push_enabled = self.config.get('enable_push_notifications', False)
        self.push_service_url = self.config.get('push_service_url', '')

        # Start notification thread
        self.notification_thread = None
        self.running = False
        self.notification_queue = []

        self.start()

    def start(self):
        """Start the notification system"""
        if not self.running:
            self.running = True
            self.notification_thread = threading.Thread(target=self._process_notifications, daemon=True)
            self.notification_thread.start()
            self.logger.info("Notification system started")

    def stop(self):
        """Stop the notification system"""
        self.running = False
        if self.notification_thread:
            self.notification_thread.join(timeout=5)
        self.logger.info("Notification system stopped")

    def add_notification_callback(self, callback: Callable):
        """Add a callback function for notifications"""
        self.notification_callbacks.append(callback)

    def remove_notification_callback(self, callback: Callable):
        """Remove a notification callback"""
        if callback in self.notification_callbacks:
            self.notification_callbacks.remove(callback)

    def notify(self, notification_type: str, message: str, data: Optional[Dict] = None,
              priority: str = 'normal', sound_alert: bool = True):
        """Send a notification"""
        current_time = datetime.now()

        # Rate limiting check
        if notification_type in self.last_notification_time:
            time_diff = current_time - self.last_notification_time[notification_type]
            if time_diff < self.min_notification_interval:
                return  # Skip notification due to rate limiting

        self.last_notification_time[notification_type] = current_time

        notification = {
            'type': notification_type,
            'message': message,
            'data': data or {},
            'priority': priority,
            'timestamp': current_time.isoformat(),
            'sound_alert': sound_alert
        }

        # Add to queue for processing
        self.notification_queue.append(notification)

        # Process immediately for high priority notifications
        if priority == 'high':
            self._process_notification(notification)

    def _process_notifications(self):
        """Background thread to process notification queue"""
        while self.running:
            if self.notification_queue:
                notification = self.notification_queue.pop(0)
                self._process_notification(notification)

            time.sleep(0.1)  # Small delay to prevent busy waiting

    def _process_notification(self, notification: Dict):
        """Process a single notification"""
        try:
            # Add to history
            self.notification_history.append(notification)
            if len(self.notification_history) > 1000:  # Keep last 1000 notifications
                self.notification_history.pop(0)

            # Call callbacks
            for callback in self.notification_callbacks:
                try:
                    callback(notification)
                except Exception as e:
                    self.logger.error(f"Notification callback error: {e}")

            # Send different types of notifications
            if notification['sound_alert'] and self.sound_enabled:
                self._play_sound_alert(notification)

            if self.email_enabled and notification['priority'] in ['high', 'critical']:
                self._send_email_notification(notification)

            if self.push_enabled:
                self._send_push_notification(notification)

            self.logger.info(f"Processed notification: {notification['type']} - {notification['message']}")

        except Exception as e:
            self.logger.error(f"Error processing notification: {e}")

    def _play_sound_alert(self, notification: Dict):
        """Play sound alert for notification"""
        try:
            # This would integrate with system audio
            # For now, we'll just log it
            sound_type = 'alert' if notification['priority'] == 'high' else 'info'
            self.logger.info(f"Sound alert: {sound_type} - {notification['message']}")

            # In a real implementation, you would use:
            # import pygame
            # pygame.mixer.init()
            # sound = pygame.mixer.Sound(f'sounds/{sound_type}.wav')
            # sound.set_volume(self.sound_volume / 100)
            # sound.play()

        except Exception as e:
            self.logger.error(f"Error playing sound alert: {e}")

    def _send_email_notification(self, notification: Dict):
        """Send email notification"""
        try:
            if not self.email_config:
                return

            smtp_server = self.email_config.get('smtp_server', '')
            smtp_port = self.email_config.get('smtp_port', 587)
            smtp_username = self.email_config.get('smtp_username', '')
            smtp_password = self.email_config.get('smtp_password', '')
            recipients = self.email_config.get('recipients', [])

            if not all([smtp_server, smtp_username, recipients]):
                self.logger.warning("Email configuration incomplete")
                return

            # Create message
            msg = MIMEMultipart()
            msg['From'] = smtp_username
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = f"GestureGuardAI Alert: {notification['type'].title()}"

            body = f"""
GestureGuardAI Notification

Type: {notification['type']}
Priority: {notification['priority']}
Time: {notification['timestamp']}

Message: {notification['message']}

Data: {json.dumps(notification['data'], indent=2)}
"""

            msg.attach(MIMEText(body, 'plain'))

            # Send email
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
            server.quit()

            self.logger.info(f"Email notification sent to {len(recipients)} recipients")

        except Exception as e:
            self.logger.error(f"Error sending email notification: {e}")

    def _send_push_notification(self, notification: Dict):
        """Send push notification"""
        try:
            if not self.push_service_url:
                return

            payload = {
                'type': notification['type'],
                'message': notification['message'],
                'data': notification['data'],
                'priority': notification['priority'],
                'timestamp': notification['timestamp']
            }

            response = requests.post(
                self.push_service_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=5
            )

            if response.status_code == 200:
                self.logger.info("Push notification sent successfully")
            else:
                self.logger.warning(f"Push notification failed: {response.status_code}")

        except Exception as e:
            self.logger.error(f"Error sending push notification: {e}")

    def notify_gesture_detected(self, gesture: str, confidence: float, hand_id: int = 0):
        """Notify about gesture detection"""
        priority = 'high' if confidence > 0.9 else 'normal'

        self.notify(
            notification_type='gesture_detected',
            message=f"Gesture '{gesture}' detected with {confidence:.2f} confidence",
            data={
                'gesture': gesture,
                'confidence': confidence,
                'hand_id': hand_id
            },
            priority=priority,
            sound_alert=True
        )

    def notify_system_status(self, status: str, details: Optional[str] = None):
        """Notify about system status changes"""
        self.notify(
            notification_type='system_status',
            message=f"System status: {status}",
            data={'status': status, 'details': details},
            priority='normal',
            sound_alert=False
        )

    def notify_error(self, error_message: str, error_details: Optional[Dict] = None):
        """Notify about system errors"""
        self.notify(
            notification_type='system_error',
            message=f"System error: {error_message}",
            data=error_details or {},
            priority='high',
            sound_alert=True
        )

    def get_notification_history(self, limit: int = 50) -> List[Dict]:
        """Get notification history"""
        return self.notification_history[-limit:].copy()

    def clear_notification_history(self):
        """Clear notification history"""
        self.notification_history.clear()

    def get_notification_stats(self) -> Dict[str, Any]:
        """Get notification statistics"""
        if not self.notification_history:
            return {'total': 0, 'by_type': {}, 'by_priority': {}}

        stats = {'total': len(self.notification_history)}

        # Count by type
        type_counts = {}
        priority_counts = {}

        for notification in self.notification_history:
            notif_type = notification['type']
            priority = notification['priority']

            type_counts[notif_type] = type_counts.get(notif_type, 0) + 1
            priority_counts[priority] = priority_counts.get(priority, 0) + 1

        stats['by_type'] = type_counts
        stats['by_priority'] = priority_counts

        return stats

# Global notification manager instance
notification_manager = NotificationManager()

def notify_gesture_detected(gesture: str, confidence: float, hand_id: int = 0):
    """Convenience function for gesture detection notifications"""
    notification_manager.notify_gesture_detected(gesture, confidence, hand_id)

def notify_system_status(status: str, details: Optional[str] = None):
    """Convenience function for system status notifications"""
    notification_manager.notify_system_status(status, details)

def notify_error(error_message: str, error_details: Optional[Dict] = None):
    """Convenience function for error notifications"""
    notification_manager.notify_error(error_message, error_details)
