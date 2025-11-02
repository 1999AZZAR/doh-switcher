from urllib.parse import urlparse
from app.services.network_service import ping_provider
from app.utils.logging import log_event

def normalize_url(url):
    """Normalize URL by removing trailing slashes and ensuring scheme."""
    parsed = urlparse(url)
    if not parsed.scheme:
        url = f"https://{url}"
        parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"

def validate_doh_url(url):
    """Validate a DoH URL by pinging its hostname."""
    try:
        ping_result = ping_provider(url)
        if ping_result == "Failed" or ping_result == "N/A":
            log_event(
                f"DoH validation failed for {url}: Ping failed or no RTT", "error"
            )
            return False
        log_event(f"DoH validation succeeded for {url}: Ping RTT={ping_result}ms")
        return True
    except Exception as e:
        log_event(f"DoH validation error for {url}: {e}", "error")
        return False
