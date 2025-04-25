#!/usr/bin/env bash
set -e

# This script installs and configures DNS over HTTPS (DoH) using cloudflared
# Usage: sudo ./install.sh

# ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging functions
step() { echo -e "${BLUE}[STEP]${NC} $*"; }
info() { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Ensure running as root
if [ "$(id -u)" -ne 0 ]; then
  error "Please run this script as root or with sudo"
  exit 1
fi

# Default DoH upstream
UPSTREAM="https://cloudflare-dns.com/dns-query"

# Banner and confirmation
info "=== DNS-over-HTTPS (DoH) Installer ==="
read -p $'\033[1;33mProceed with installation? [y/N]: \033[0m' confirm
if [[ ! "$confirm" =~ ^[Yy] ]]; then
  error "Aborted by user."
  exit 1
fi

# Ask for custom DoH upstream
read -p $'\033[1;33mUse default DoH upstream? [Y/n]: \033[0m' use_default
if [[ "$use_default" =~ ^[Nn] ]]; then
  read -p $'\033[1;33mEnter custom DoH URL: \033[0m' custom_url
  UPSTREAM="${custom_url:-$UPSTREAM}"
fi
step "Using DoH upstream: $UPSTREAM"

step "Updating package index..."
apt-get update -y

step "Downloading cloudflared..."
wget -q -O /tmp/cloudflared.deb \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb

step "Installing cloudflared..."
dpkg -i /tmp/cloudflared.deb || apt-get install -f -y

step "Verifying installation"
cloudflared --version

step "Creating service user..."
if ! id cloudflared &>/dev/null; then
  useradd -r -s /usr/sbin/nologin cloudflared
fi

step "Creating systemd service..."
cat > /etc/systemd/system/cloudflared.service <<EOF
[Unit]
Description=cloudflared DNS over HTTPS proxy
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=10

[Service]
Type=simple
ExecStart=/usr/bin/cloudflared proxy-dns --port 53 --upstream $UPSTREAM
User=cloudflared
Restart=always
RestartSec=2
TimeoutStopSec=20
LimitNOFILE=4096

[Install]
WantedBy=multi-user.target
EOF

step "Granting permissions to bind port 53..."
setcap 'cap_net_bind_service=+ep' /usr/bin/cloudflared

step "Enabling and starting service..."
systemctl daemon-reload
enable cloudflared || systemctl enable cloudflared
systemctl start cloudflared

step "Disabling systemd-resolved..."
systemctl stop systemd-resolved
enable systemd-resolved && systemctl disable systemd-resolved || true
systemctl disable systemd-resolved || true

step "Updating resolv.conf..."
rm -f /etc/resolv.conf
echo "nameserver 127.0.0.1" > /etc/resolv.conf

step "Configuring firewall..."
iptables -C INPUT -p tcp --dport 53 -j ACCEPT 2>/dev/null || \
  iptables -I INPUT -p tcp --dport 53 -j ACCEPT
iptables -C INPUT -p udp --dport 53 -j ACCEPT 2>/dev/null || \
  iptables -I INPUT -p udp --dport 53 -j ACCEPT

step "Setting up auto-restart on network changes..."
apt-get install -y networkd-dispatcher
mkdir -p /etc/networkd-dispatcher/routable.d
cat > /etc/networkd-dispatcher/routable.d/restart-cloudflared.sh <<EOF
#!/bin/bash
systemctl restart cloudflared
EOF
chmod +x /etc/networkd-dispatcher/routable.d/restart-cloudflared.sh
systemctl daemon-reload
systemctl restart networkd-dispatcher

info "Setup complete. Verify with: sudo lsof -i :53"
