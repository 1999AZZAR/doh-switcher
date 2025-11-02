import json
import os
from app.models import PROVIDERS_FILE, BACKUP_FILE, DEFAULT_PROVIDERS
from app.utils.logging import log_event
from flask import flash

def initialize_providers_file():
    """Create doh_providers.json with default providers if it doesn't exist."""
    if not os.path.exists(PROVIDERS_FILE):
        try:
            with open(PROVIDERS_FILE, "w") as file:
                json.dump(DEFAULT_PROVIDERS, file, indent=4)
            log_event(f"Created {PROVIDERS_FILE} with default providers.")
        except IOError as e:
            log_event(f"Error creating {PROVIDERS_FILE}: {e}", "error")
            flash(f"Error creating providers file: {e}", "danger")

def load_providers():
    """Load providers from file or initialize with defaults."""
    initialize_providers_file()
    try:
        with open(PROVIDERS_FILE, "r") as file:
            providers = json.load(file)
            for provider in providers:
                if not all(key in provider for key in ["name", "url"]):
                    raise ValueError("Invalid provider format")
            return providers
    except (json.JSONDecodeError, IOError, ValueError) as e:
        log_event(f"Error loading providers file: {e}", "error")
        flash(f"Error loading providers file: {e}", "danger")
        return DEFAULT_PROVIDERS

def save_providers(providers):
    """Save providers to file."""
    try:
        with open(PROVIDERS_FILE, "w") as file:
            json.dump(providers, file, indent=4)
        log_event("Providers saved successfully.")
    except IOError as e:
        log_event(f"Error saving providers file: {e}", "error")
        flash(f"Error saving providers: {e}", "danger")
        raise

def backup_config():
    """Backup providers configuration."""
    try:
        with open(PROVIDERS_FILE, "r") as src, open(BACKUP_FILE, "w") as dst:
            dst.write(src.read())
        log_event("Configuration backed up.")
        return True
    except IOError as e:
        log_event(f"Error backing up configuration: {e}", "error")
        return False

def restore_config():
    """Restore providers configuration from backup."""
    if not os.path.exists(BACKUP_FILE):
        return False
    try:
        with open(BACKUP_FILE, "r") as src, open(PROVIDERS_FILE, "w") as dst:
            dst.write(src.read())
        log_event("Configuration restored.")
        return True
    except IOError as e:
        log_event(f"Error restoring configuration: {e}", "error")
        return False
