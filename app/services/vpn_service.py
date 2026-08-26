import subprocess
import os
from app.services.dns_service import set_system_dns

def is_vpn_mode_active():
    """Check if the VPN stack (warp-cli or dnscrypt-proxy) is currently running."""
    try:
        res = subprocess.run(["/usr/bin/systemctl", "is-active", "unbound"], capture_output=True, text=True)
        return res.stdout.strip() == "active"
    except Exception as e:
        print(f"Error in is_vpn_mode_active: {e}")
        return False

def enable_vpn_mode():
    """Stops cloudflared and starts unbound, dnscrypt-proxy, and warp-cli."""
    try:
        subprocess.run(["/usr/bin/systemctl", "stop", "cloudflared"], check=False)
        subprocess.run(["/usr/bin/systemctl", "disable", "cloudflared"], check=False)
        
        subprocess.run(["/usr/bin/systemctl", "start", "dnscrypt-proxy"], check=True)
        subprocess.run(["/usr/bin/systemctl", "enable", "dnscrypt-proxy"], check=False)
        subprocess.run(["/usr/bin/systemctl", "start", "unbound"], check=True)
        subprocess.run(["/usr/bin/systemctl", "enable", "unbound"], check=False)
        
        subprocess.run(["/usr/bin/warp-cli", "--accept-tos", "registration", "new"], check=False)
        subprocess.run(["/usr/bin/warp-cli", "--accept-tos", "mode", "tunnel_only"], check=True)
        subprocess.run(["/usr/bin/warp-cli", "--accept-tos", "connect"], check=True)

        set_system_dns("127.0.0.1")
        
        return True
    except Exception as e:
        print(f"Error enabling VPN mode: {e}")
        return False

def disable_vpn_mode():
    """Stops the VPN stack and restores cloudflared."""
    try:
        subprocess.run(["/usr/bin/warp-cli", "--accept-tos", "disconnect"], check=False)
        
        subprocess.run(["/usr/bin/systemctl", "stop", "unbound"], check=False)
        subprocess.run(["/usr/bin/systemctl", "disable", "unbound"], check=False)
        subprocess.run(["/usr/bin/systemctl", "stop", "dnscrypt-proxy"], check=False)
        subprocess.run(["/usr/bin/systemctl", "disable", "dnscrypt-proxy"], check=False)
        
        subprocess.run(["/usr/bin/systemctl", "start", "cloudflared"], check=True)
        subprocess.run(["/usr/bin/systemctl", "enable", "cloudflared"], check=False)

        set_system_dns("127.0.0.1")
        
        return True
    except Exception as e:
        print(f"Error disabling VPN mode: {e}")
        return False
