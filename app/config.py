"""Configuration loader for Gasket Gateway."""

import os

import yaml

DEFAULTS = {
    "server": {
        "host": "0.0.0.0",
        "port": 5000,
        "metrics_port": 9050,
        "debug": False,
    },
    "default_theme": "dark",
    "banners": [],
    "oidc": {
        "provider_url": "",
        "client_id": "",
        "client_secret": "",
        "skip_tls_verify": False,
        "session_timeout_hours": 8,
        "logout_url": "",
        "groups": {
            "user_access": "gasket-users",
            "admin_access": "gasket-admins",
        },
    },
    "database": {
        "host": "localhost",
        "port": 5432,
        "name": "gasket",
        "user": "gasket",
        "password": "",
    },
    "opensearch": {
        "url": "http://localhost:9200",
        "skip_tls_verify": False,
    },
    "backend_profiles": [],
    "openai_backends": [],
}


def _deep_merge(base, override):
    """Recursively merge override dict into base dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path=None):
    """Load configuration from YAML file, merged over defaults."""
    config = DEFAULTS.copy()

    if path and os.path.isfile(path):
        with open(path, "r") as f:
            file_config = yaml.safe_load(f) or {}
        config = _deep_merge(config, file_config)

    return config
