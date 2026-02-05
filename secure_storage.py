"""
Secure Storage Module
Handles secure storage of sensitive credentials using OS keyring.
Falls back to config file if keyring is unavailable.
"""

import keyring
from typing import Optional

SERVICE_NAME = "PrismDesktop"
TOKEN_KEY = "ha_token"


def is_keyring_available() -> bool:
    """Check if keyring backend is available and functional."""
    try:
        # Try a test operation to verify keyring works
        keyring.get_keyring()
        return True
    except Exception:
        return False


def store_token(token: str) -> bool:
    """
    Store the Home Assistant token securely in the OS keyring.
    
    Args:
        token: The Home Assistant long-lived access token.
        
    Returns:
        True if stored successfully, False otherwise.
    """
    if not token:
        return False
    try:
        keyring.set_password(SERVICE_NAME, TOKEN_KEY, token)
        return True
    except Exception as e:
        print(f"Failed to store token in keyring: {e}")
        return False


def get_token() -> Optional[str]:
    """
    Retrieve the Home Assistant token from the OS keyring.
    
    Returns:
        The token if found, None otherwise.
    """
    try:
        return keyring.get_password(SERVICE_NAME, TOKEN_KEY)
    except Exception as e:
        print(f"Failed to retrieve token from keyring: {e}")
        return None


def delete_token() -> bool:
    """
    Delete the Home Assistant token from the OS keyring.
    
    Returns:
        True if deleted successfully, False otherwise.
    """
    try:
        keyring.delete_password(SERVICE_NAME, TOKEN_KEY)
        return True
    except keyring.errors.PasswordDeleteError:
        # Token doesn't exist, that's fine
        return True
    except Exception as e:
        print(f"Failed to delete token from keyring: {e}")
        return False


def migrate_token_to_keyring(config: dict) -> dict:
    """
    Migrate token from plaintext config to secure keyring storage.
    
    Args:
        config: The configuration dictionary.
        
    Returns:
        Updated config dict with token removed (if migration successful).
    """
    ha_config = config.get('home_assistant', {})
    plaintext_token = ha_config.get('token', '')
    
    if plaintext_token and is_keyring_available():
        if store_token(plaintext_token):
            # Remove token from config, keep a flag indicating keyring is used
            ha_config['token'] = ''
            ha_config['use_keyring'] = True
            config['home_assistant'] = ha_config
            print("Token migrated to secure keyring storage")
    
    return config


def get_effective_token(config: dict) -> str:
    """
    Get the token from keyring if available, otherwise from config.
    
    Args:
        config: The configuration dictionary.
        
    Returns:
        The Home Assistant token.
    """
    ha_config = config.get('home_assistant', {})
    
    # Try keyring first if enabled
    if ha_config.get('use_keyring', False) or is_keyring_available():
        keyring_token = get_token()
        if keyring_token:
            return keyring_token
    
    # Fall back to config (for backwards compatibility or if keyring unavailable)
    return ha_config.get('token', '')


def save_token_securely(token: str, config: dict) -> dict:
    """
    Save token to keyring if available, otherwise to config.
    
    Args:
        token: The token to save.
        config: The configuration dictionary.
        
    Returns:
        Updated config dict.
    """
    if 'home_assistant' not in config:
        config['home_assistant'] = {}
    
    if is_keyring_available() and store_token(token):
        config['home_assistant']['token'] = ''
        config['home_assistant']['use_keyring'] = True
    else:
        # Fallback: store in config (less secure)
        config['home_assistant']['token'] = token
        config['home_assistant']['use_keyring'] = False
        print("Warning: Keyring unavailable, token stored in config file")
    
    return config
