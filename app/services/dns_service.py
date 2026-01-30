import subprocess
import re
import requests
import socket
from urllib.parse import urlparse
from app.models import SERVICE_FILES
from app.utils.logging import log_event
from app.utils.validators import normalize_url, is_valid_ip
from flask import flash

RESOLV_CONF = "/etc/resolv.conf"

def get_provider_type(url):
    if is_valid_ip(url):
        return "plain"
    if url.startswith("tls://"):
        return "dot"
    return "doh"

def set_system_dns(nameserver):
    """Update /etc/resolv.conf with the specified nameserver."""
    try:
        # Check if systemd-resolved is active, if so we might need to use resolvectl
        # But install.sh disabled it. Assuming direct /etc/resolv.conf access.
        with open(RESOLV_CONF, "w") as f:
            f.write(f"nameserver {nameserver}\n")
        log_event(f"Updated system DNS to {nameserver}")
    except IOError as e:
        log_event(f"Error updating resolv.conf: {e}", "error")
        raise

def update_dns_service(url):
    """Update the DNS configuration (Cloudflared or System)."""
    p_type = get_provider_type(url)
    
    try:
        if p_type == "plain":
            # Stop cloudflared to avoid conflicts/resources
            control_service("stop")
            # Set system DNS
            set_system_dns(url)
            log_event(f"Switched to Plain DNS: {url}")
            
        else:
            # DoH or DoT
            # Ensure system points to local cloudflared
            set_system_dns("127.0.0.1")
            
            # Update cloudflared config
            service_file = SERVICE_FILES[0]
            with open(service_file, "r") as file:
                lines = file.readlines()

            with open(service_file, "w") as file:
                for line in lines:
                    if line.strip().startswith("ExecStart="):
                        # Cloudflared supports https:// and tls:// in --upstream
                        file.write(
                            f"ExecStart=/usr/bin/cloudflared proxy-dns --port 53 --upstream {url}\n"
                        )
                    else:
                        file.write(line)

            subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
            control_service("restart")
            log_event(f"Updated Cloudflared upstream to: {url}")
            
    except (IOError, subprocess.CalledProcessError) as e:
        log_event(f"Error updating DNS service: {e}", "error")
        flash(f"Error updating service: {e}", "danger")
        raise

def get_current_provider():
    """Get the current DNS provider (DoH/DoT/Plain)."""
    try:
        # Check resolv.conf first
        with open(RESOLV_CONF, "r") as f:
            content = f.read()
            
        match_ns = re.search(r"nameserver\s+([\d\.]+)", content)
        if match_ns:
            ns_ip = match_ns.group(1)
            if ns_ip != "127.0.0.1":
                # It's Plain DNS
                # Find name if possible
                from app.services.provider_service import load_providers
                providers = load_providers()
                for provider in providers:
                    if provider["url"] == ns_ip:
                         return provider["name"], ns_ip, ns_ip
                return f"Plain DNS ({ns_ip})", ns_ip, ns_ip
        
        # If 127.0.0.1, check cloudflared
        with open(SERVICE_FILES[0], "r") as file:
            content = file.read()
            # Match http or tls
            match = re.search(r"--upstream\s+((?:https?|tls)://[^\s/]+(?:/[^\s]*)?)", content)
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
        log_event(f"Error reading configuration: {e}", "error")
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

def test_provider_resolution(url):
    """Test resolution for the provider."""
    p_type = get_provider_type(url)
    
    if p_type == "doh":
        try:
            r = requests.get(f"{url}?name=example.com&type=A", headers={"Accept":"application/dns-json"}, timeout=3)
            data = r.json()
            return "Answer" in data and bool(data.get("Answer"))
        except:
            return False
    elif p_type == "plain":
        try:
            # Use dig to test specific server
            cmd = ["dig", "@" + url, "+short", "example.com", "A"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            return res.returncode == 0 and bool(res.stdout.strip())
        except:
            return False
    else: # DoT
        # Try a basic TCP connection to port 853
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname
            # Use 853 as default DoT port
            with socket.create_connection((hostname, 853), timeout=3):
                pass
            return True 
        except:
            return False