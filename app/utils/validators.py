from urllib.parse import urlparse
import ipaddress
from app.services.network_service import ping_provider
from app.utils.logging import log_event

def is_valid_ip(address):
    """Check if the string is a valid IP address."""
    try:
        ipaddress.ip_address(address)
        return True
    except ValueError:
        return False

def normalize_url(url):
    """Normalize URL by removing trailing slashes and ensuring scheme."""
    url = url.strip()
    if is_valid_ip(url):
        return url
        
    parsed = urlparse(url)
    if not parsed.scheme:
        # Default to https unless it's an IP (checked above)
        url = f"https://{url}"
        parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"

def validate_provider(url):
    """Validate a Provider (DoH/DoT/IP) by pinging its hostname/IP."""
    try:
        ping_result = ping_provider(url)
        if ping_result == "Failed" or ping_result == "N/A":
            log_event(
                f"Validation failed for {url}: Ping failed or no RTT", "error"
            )
            return False
        log_event(f"Validation succeeded for {url}: Ping RTT={ping_result}ms")
        return True
    except Exception as e:
        log_event(f"Validation error for {url}: {e}", "error")
        return False