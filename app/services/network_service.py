import subprocess
import re
from app.utils.logging import log_event

def get_network_info():
    """Get current network information."""
    info = {"local_ip": None, "gateway": None, "dns_servers": []}
    try:
        result = subprocess.run(["ip", "route", "get", "8.8.8.8"], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            m = re.search(r"src\s+(\S+)", result.stdout)
            if m:
                info["local_ip"] = m.group(1)
            m2 = re.search(r"via\s+(\S+)", result.stdout)
            if m2:
                info["gateway"] = m2.group(1)
    except Exception as e:
        log_event(f"Error getting network route info: {e}", "error")
    try:
        with open("/etc/resolv.conf") as f:
            for line in f:
                if line.startswith("nameserver"):
                    parts = line.split()
                    if len(parts) >= 2:
                        info["dns_servers"].append(parts[1])
    except Exception as e:
        log_event(f"Error reading resolv.conf: {e}", "error")
    return info

def ping_provider(url):
    """Ping the provider's hostname and return the average RTT."""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        result = subprocess.run(
            ["ping", "-c", "3", "-W", "2", hostname], capture_output=True, text=True
        )
        if result.returncode == 0:
            match = re.search(r"rtt min/avg/max/mdev = [\d.]+/([\d.]+)/", result.stdout)
            if match:
                return round(float(match.group(1)), 2)
            return "N/A"
        return "Failed"
    except Exception as e:
        log_event(f"Ping error for {url}: {e}", "error")
        return "Failed"
