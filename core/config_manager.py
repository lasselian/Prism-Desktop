import json
import copy
import keyring
from typing import Optional
from pathlib import Path
from core.utils import get_config_path

SERVICE_NAME = "PrismDesktop"
KEY_TOKEN = "ha_token"

class ConfigManager:
    """Manages application configuration and keyring tokens."""
    
    def __init__(self, config_filename: str = "config.json"):
        self.config_path = get_config_path(config_filename)
        self.config = self.load_config()
        self.save_config()  # Scrub sensitive data (tokens) from disk immediately

    def get(self, key: str, default=None):
        return self.config.get(key, default)
        
    def __getitem__(self, key):
        return self.config[key]
        
    def __setitem__(self, key, value):
        self.config[key] = value

    def load_config(self) -> dict:
        """Load configuration from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                    # --- Keyring Migration & Loading ---
                    ha_config = config.get('home_assistant', {})
                    token_in_file = ha_config.get('token', '')
                    
                    token_from_keyring = None
                    try:
                        token_from_keyring = keyring.get_password(SERVICE_NAME, KEY_TOKEN)
                    except Exception as e:
                        print(f"Keyring read error: {e}")
                    
                    if token_from_keyring:
                        ha_config['token'] = token_from_keyring
                    elif token_in_file:
                        print("Migrating token to keyring...")
                        try:
                            keyring.set_password(SERVICE_NAME, KEY_TOKEN, token_in_file)
                            if keyring.get_password(SERVICE_NAME, KEY_TOKEN) == token_in_file:
                                print("Migration successful.")
                                ha_config['token'] = '' 
                                self.save_raw_config(config)
                                ha_config['token'] = token_in_file
                        except Exception as e:
                            print(f"Migration failed: {e}")
                    
                    # --- Auto-migrate legacy slot-only configs to (row, col) ---
                    cols = config.get('appearance', {}).get('cols', 4)
                    for btn_cfg in config.get('buttons', []):
                        if 'row' not in btn_cfg and 'slot' in btn_cfg:
                            slot = btn_cfg['slot']
                            btn_cfg['row'] = slot // cols
                            btn_cfg['col'] = slot % cols
                    
                    return config
            except Exception as e:
                print(f"Error loading config: {e}")
        
        return {
            "home_assistant": {"url": "", "token": ""},
            "appearance": {"theme": "system", "rows": 2, "button_style": "Gradient"},
            "shortcut": {"type": "keyboard", "value": "<ctrl>+<alt>+h"},
            "buttons": []
        }

    def save_raw_config(self, config_to_save: dict):
        """Save a specific config dict without modifying self.config."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, indent=2)
        except Exception as e:
            print(f"Error saving raw config: {e}")

    def save_config(self):
        """Save current configuration to file."""
        try:
            config_to_save = copy.deepcopy(self.config)
            ha_config = config_to_save.get('home_assistant', {})
            token = ha_config.get('token', '')
            
            if token:
                try:
                    keyring.set_password(SERVICE_NAME, KEY_TOKEN, token)
                    ha_config['token'] = '' 
                except Exception as e:
                    print(f"Keyring write error: {e}")
                    ha_config['token'] = '' 
            
            self.save_raw_config(config_to_save)
        except Exception as e:
            print(f"Error saving config: {e}")
