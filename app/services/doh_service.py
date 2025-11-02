import subprocess
import re
import requests
from app.models import SERVICE_FILES
from app.utils.logging import log_event
from app.utils.validators import normalize_url
from flask import flash

def update_doh_service(doh_url):
    """Update the cloudflared service with the new DoH URL."""
    service_file = SERVICE_FILES[0]
    try:
        with open(service_file, "r") as file:
            lines = file.readlines()

        with open(service_file, "w") as file:
            for line in lines:
                if line.strip().startswith("ExecStart="):
                    file.write(
                        f"ExecStart=/usr/bin/cloudflared proxy-dns --port 53 --upstream {doh_url}\n"
                    )
                else:
                    file.write(line)

        subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
        subprocess.run(["sudo", "systemctl", "restart", "cloudflared"], check=True)
        log_event(f"Updated DoH URL to: {doh_url}")
    except (IOError, subprocess.CalledProcessError) as e:
        log_event(f"Error updating service file: {e}", "error")
        flash(f"Error updating service: {e}", "danger")
        raise

def get_current_doh_provider():
    """Get the current DoH provider from the service file."""
    try:
        with open(SERVICE_FILES[0], "r") as file:
            content = file.read()
            match = re.search(r"--upstream\s+(https?://[^\s/]+(?:/[^\s]*)?)", content)
            if match:
                full_url = match.group(1)
                base_url = normalize_url(full_url)
                from app.services.provider_service import load_providers
                providers = load_providers()
                for provider in providers:
                    if normalize_url(provider["url"]) == base_url:
                        return provider["name"], full_url, base_url
                return f"Unknown ({full_url})", full_url, base_url
        return "Unknown", "Unknown", "Unknown"
    except IOError as e:
        log_event(f"Error reading service file: {e}", "error")
        flash(f"Error reading service file: {e}", "danger")
        return "Unknown", "Unknown", "Unknown"

def get_service_status():
    """Check if the cloudflared service is running."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", "cloudflared"], check=False
        )
        return "running" if result.returncode == 0 else "not running"
    except subprocess.CalledProcessError as e:
        log_event(f"Error checking service status: {e}", "error")
        return "not running"

def control_service(action):
    """Control cloudflared service (start/stop/restart)."""
    try:
        subprocess.run(["sudo", "systemctl", action, "cloudflared"], check=True)
        log_event(f"Service {action}ed.")
        return True
    except subprocess.CalledProcessError as e:
        log_event(f"Error {action}ing service: {e}", "error")
        return False

def doh_query_test(url):
    """Perform a DNS-over-HTTPS query to validate service."""
    try:
        r = requests.get(f"{url}?name=example.com&type=A", headers={"Accept":"application/dns-json"}, timeout=3)
        data = r.json()
        return "Answer" in data and bool(data.get("Answer"))
    except Exception as e:
        log_event(f"DoH query error for {url}: {e}", "error")
        return False
