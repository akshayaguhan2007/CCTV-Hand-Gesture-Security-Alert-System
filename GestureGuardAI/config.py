import os
import json
from typing import Dict, Any, Optional
from pathlib import Path

class ConfigManager:
    """Centralized configuration management for GestureGuardAI"""

    def __init__(self, config_file: str = 'config.json'):
        self.config_file = Path(config_file)
        self.default_config = {
            # Detection settings
            'detection': {
                'min_detection_confidence': 0.8,
                'min_tracking_confidence': 0.7,
                'gesture_stability_frames': 5,
                'max_hands': 2,
                'enable_gesture_classification': True,
                'detection_interval_ms': 100,
                'frame_skip_rate': 1
            },

            # Logging settings
            'logging': {
                'log_level': 'INFO',
                'log_to_file': True,
                'log_file_path': 'logs/gesture_guard.log',
                'max_log_files': 10,
                'log_rotation_size_mb': 10,
                'enable_console_logging': True
            },

            # Database settings
            'database': {
                'path': 'database.db',
                'backup_enabled': True,
                'backup_interval_hours': 24,
                'backup_retention_days': 30,
                'auto_cleanup_days': 30
            },

            # Camera settings
            'camera': {
                'width': 640,
                'height': 480,
                'fps': 30,
                'camera_id': 0,
                'auto_focus': True,
                'brightness': 50,
                'contrast': 50
            },

            # Web server settings
            'server': {
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False,
                'threaded': True,
                'ssl_enabled': False,
                'ssl_cert_path': '',
                'ssl_key_path': ''
            },

            # Session settings
            'session': {
                'session_timeout_minutes': 30,
                'max_concurrent_sessions': 5,
                'enable_session_tracking': True,
                'session_cleanup_interval_minutes': 5
            },

            # Export settings
            'export': {
                'default_format': 'csv',
                'export_directory': 'exports',
                'max_export_records': 10000,
                'enable_auto_export': False,
                'auto_export_interval_hours': 24
            },

            # Notification settings
            'notifications': {
                'enable_sound_alerts': True,
                'sound_volume': 50,
                'enable_email_notifications': False,
                'email_recipients': [],
                'smtp_server': '',
                'smtp_port': 587,
                'smtp_username': '',
                'smtp_password': '',
                'enable_push_notifications': False,
                'push_service_url': ''
            },

            # UI settings
            'ui': {
                'theme': 'auto',
                'refresh_interval_ms': 1000,
                'enable_animations': True,
                'chart_update_interval_ms': 5000,
                'max_display_logs': 50
            },

            # Performance settings
            'performance': {
                'enable_gpu_acceleration': True,
                'max_memory_usage_mb': 1024,
                'enable_frame_caching': True,
                'cache_size_mb': 100,
                'processing_threads': 2
            },

            # Security settings
            'security': {
                'enable_authentication': True,
                'default_username': 'admin',
                'default_password': 'admin123',
                'session_secret_key': 'change_this_in_production',
                'enable_https_redirect': False,
                'allowed_hosts': ['localhost', '127.0.0.1']
            }
        }

        self.config = self.load_config()

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    user_config = json.load(f)
                # Merge user config with defaults
                return self._deep_merge(self.default_config, user_config)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"Warning: Could not load config file: {e}")
                return self.default_config.copy()
        else:
            # Create default config file
            self.save_config(self.default_config)
            return self.default_config.copy()

    def save_config(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Save configuration to file"""
        if config is None:
            config = self.config

        try:
            # Create directory if it doesn't exist
            self.config_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def get(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation (e.g., 'detection.min_detection_confidence')"""
        keys = key_path.split('.')
        value = self.config

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key_path: str, value: Any) -> bool:
        """Set configuration value using dot notation"""
        keys = key_path.split('.')
        config = self.config

        try:
            # Navigate to parent of target key
            for key in keys[:-1]:
                if key not in config:
                    config[key] = {}
                config = config[key]

            # Set the value
            config[keys[-1]] = value
            return self.save_config()
        except Exception as e:
            print(f"Error setting config value: {e}")
            return False

    def update_section(self, section: str, values: Dict[str, Any]) -> bool:
        """Update an entire configuration section"""
        if section not in self.config:
            self.config[section] = {}

        self.config[section].update(values)
        return self.save_config()

    def reset_to_defaults(self) -> bool:
        """Reset configuration to default values"""
        self.config = self.default_config.copy()
        return self.save_config()

    def get_section(self, section: str) -> Dict[str, Any]:
        """Get an entire configuration section"""
        return self.config.get(section, {}).copy()

    def validate_config(self) -> List[str]:
        """Validate configuration and return list of issues"""
        issues = []

        # Validate detection settings
        detection_conf = self.get('detection.min_detection_confidence', 0)
        if not 0 < detection_conf <= 1:
            issues.append("Detection confidence must be between 0 and 1")

        tracking_conf = self.get('detection.min_tracking_confidence', 0)
        if not 0 < tracking_conf <= 1:
            issues.append("Tracking confidence must be between 0 and 1")

        # Validate camera settings
        width = self.get('camera.width', 0)
        height = self.get('camera.height', 0)
        if width <= 0 or height <= 0:
            issues.append("Camera width and height must be positive")

        # Validate server settings
        port = self.get('server.port', 0)
        if not 1 <= port <= 65535:
            issues.append("Server port must be between 1 and 65535")

        return issues

    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries"""
        result = base.copy()

        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def export_config(self, filepath: str) -> bool:
        """Export current configuration to file"""
        try:
            with open(filepath, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error exporting config: {e}")
            return False

    def import_config(self, filepath: str) -> bool:
        """Import configuration from file"""
        try:
            with open(filepath, 'r') as f:
                imported_config = json.load(f)

            self.config = self._deep_merge(self.default_config, imported_config)
            return self.save_config()
        except Exception as e:
            print(f"Error importing config: {e}")
            return False

    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of current configuration"""
        return {
            'detection_enabled': self.get('detection.enable_gesture_classification', True),
            'camera_resolution': f"{self.get('camera.width', 640)}x{self.get('camera.height', 480)}",
            'server_host': self.get('server.host', '0.0.0.0'),
            'server_port': self.get('server.port', 5000),
            'log_level': self.get('logging.log_level', 'INFO'),
            'total_sessions_tracked': len([k for k in self.config.keys() if k.startswith('session_')])
        }

# Global configuration instance
config_manager = ConfigManager()

def get_config(key_path: str, default: Any = None) -> Any:
    """Convenience function to get configuration values"""
    return config_manager.get(key_path, default)

def set_config(key_path: str, value: Any) -> bool:
    """Convenience function to set configuration values"""
    return config_manager.set(key_path, value)
