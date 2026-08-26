#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root or via sudo."
  exit 1
fi

echo "Installing Privacy VPN Stack (unbound, dnscrypt-proxy, warp-cli)..."

# 1. Add Cloudflare WARP repository
if ! command -v warp-cli >/dev/null; then
    echo "Adding Cloudflare WARP repository..."
    curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | sudo gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg
    echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflare-client.list
    apt-get update
    apt-get install -y cloudflare-warp
fi

# 2. Install unbound and dnscrypt-proxy
echo "Installing unbound and dnscrypt-proxy..."
apt-get install -y unbound dnscrypt-proxy

# 3. Configure dnscrypt-proxy for Quad9 (HTTP/3)
echo "Configuring dnscrypt-proxy..."
if [ -f /etc/dnscrypt-proxy/dnscrypt-proxy.toml ]; then
    cp /etc/dnscrypt-proxy/dnscrypt-proxy.toml /etc/dnscrypt-proxy/dnscrypt-proxy.toml.bak
    # Configure dual IPv4/IPv6 servers for optimal WARP speed
    sed -i "s/^#\? \?server_names = .*/server_names = ['quad9-doh-ip4-port443-nofilter-pri', 'quad9-doh-ip6-port443-nofilter-pri']/" /etc/dnscrypt-proxy/dnscrypt-proxy.toml
    sed -i "s/^#\? \?listen_addresses = .*/listen_addresses = ['127.0.0.1:5054']/" /etc/dnscrypt-proxy/dnscrypt-proxy.toml
    
    # Disable dnscrypt-proxy cache and DNSSEC (Unbound handles this better)
    if ! grep -q "require_dnssec" /etc/dnscrypt-proxy/dnscrypt-proxy.toml; then
        # Insert at the top (global section) to avoid breaking TOML syntax
        sed -i '1i require_dnssec = false\ncache = false' /etc/dnscrypt-proxy/dnscrypt-proxy.toml
    fi
fi

# 4. Configure unbound
echo "Configuring unbound..."
cat <<UNBOUND > /etc/unbound/unbound.conf.d/doh-switcher-vpn.conf
server:
    interface: 127.0.0.1
    port: 53
    do-ip4: yes
    do-udp: yes
    do-tcp: yes
    username: "unbound"
    do-not-query-localhost: no
    
    # Let Unbound handle cache and DNSSEC validation optimally
    module-config: "validator iterator"
    harden-dnssec-stripped: yes
    prefetch: yes
    cache-min-ttl: 300
    cache-max-ttl: 86400
    msg-cache-size: 50m
    rrset-cache-size: 100m
forward-zone:
    name: "."
    forward-addr: 127.0.0.1@5054
UNBOUND

# 5. Stop services so cloudflared can continue ruling until toggled
echo "Stopping and disabling VPN services by default..."
systemctl stop unbound dnscrypt-proxy || true
systemctl disable unbound dnscrypt-proxy || true

echo "VPN Stack Installation Complete."
