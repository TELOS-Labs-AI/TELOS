"""
Environment Helper for Streamlit Cloud Compatibility
====================================================

Provides utilities for detecting runtime environment and accessing
configuration in a way that works both locally and on Streamlit Cloud.
"""

import os
import streamlit as st
from pathlib import Path
from typing import Optional


def is_streamlit_cloud() -> bool:
    """
    Detect if running on Streamlit Cloud.
    
    Returns:
        bool: True if running on Streamlit Cloud, False otherwise
    """
    # Streamlit Cloud sets specific environment variables
    return (
        os.getenv('STREAMLIT_SHARING_MODE') is not None or
        os.getenv('STREAMLIT_SERVER_HEADLESS') == 'true' or
        'streamlit.io' in os.getenv('HOSTNAME', '')
    )


def get_secret(key: str, default: Optional[str] = None, section: str = "default") -> Optional[str]:
    """
    Get a secret value from Streamlit secrets or environment.
    
    Works both locally (from .streamlit/secrets.toml or .env) and on
    Streamlit Cloud (from Secrets management UI).
    
    Args:
        key: Secret key to retrieve
        default: Default value if key not found
        section: Section in secrets.toml (default: "default")
    
    Returns:
        Secret value or default
    """
    try:
        # Try Streamlit secrets first (works both locally and in cloud)
        if hasattr(st, 'secrets'):
            if section and section in st.secrets:
                if key in st.secrets[section]:
                    return st.secrets[section][key]
            # Also try top-level
            if key in st.secrets:
                return st.secrets[key]
    except Exception:
        pass
    
    # Fall back to environment variable
    value = os.getenv(key)
    if value is not None:
        return value
    
    return default


def get_api_key(service: str = "MISTRAL") -> Optional[str]:
    """
    Get API key for a specific service.
    
    Args:
        service: Service name (MISTRAL, OPENAI, etc.)
    
    Returns:
        API key or None
    """
    key_name = f"{service.upper()}_API_KEY"
    return get_secret(key_name)


def get_data_dir(subdir: str = "") -> Path:
    """
    Get data directory path that works both locally and in cloud.
    
    Args:
        subdir: Optional subdirectory within data dir
    
    Returns:
        Path to data directory
    """
    if is_streamlit_cloud():
        # On Streamlit Cloud, use /tmp for temporary data
        base_dir = Path("/tmp/telos_data")
    else:
        # Locally, use project directory
        base_dir = Path(__file__).parent.parent.parent / "data"
    
    if subdir:
        data_dir = base_dir / subdir
    else:
        data_dir = base_dir
    
    # Ensure directory exists
    data_dir.mkdir(parents=True, exist_ok=True)
    
    return data_dir


def get_beta_config(key: str, default=None):
    """
    Get beta testing configuration value.
    
    Args:
        key: Configuration key
        default: Default value if not found
    
    Returns:
        Configuration value or default
    """
    try:
        if hasattr(st, 'secrets') and 'beta' in st.secrets:
            if key in st.secrets['beta']:
                return st.secrets['beta'][key]
    except Exception:
        pass
    
    # Defaults
    defaults = {
        'enabled': True,
        'data_dir': 'beta_testing/data',
        'min_turns_for_completion': 50,
        'beta_duration_days': 14
    }
    
    return defaults.get(key, default)
