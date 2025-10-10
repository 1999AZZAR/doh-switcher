#!/usr/bin/env bash
# This script installs and configures DNS over HTTPS (DoH) using cloudflared.
# It is designed to be robust, idempotent, and handle Tailscale DNS conflicts.
# Usage: sudo ./install.sh

set -e # Exit immediately if a command exits with a non-zero status.
set -o pipefail # Return value of a pipeline is the value of the last command to exit with a non-zero status

# --- Configuration ---
# Default DoH upstream provider
DEFAULT_UPSTREAM="https://cloudflare-dns.com/dns-query"

# --- ANSI Color Codes ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# --- Logging Functions ---
# These functions print colored and prefixed messages to the console.
step() { echo -e "${BLUE}[STEP]${NC} $*"; }
info() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }
fatal() { error "$*"; exit 1; }

# --- Helper Functions ---
# Ensure the script is run as root
ensure_root() {
  if [ "$(id -u)" -ne 0 ]; then
    fatal "This script must be run as root or with sudo."
  fi
}

# Cleanup function to be called on script exit
cleanup() {
  # This function runs on any script exit, successful or not.
  # We check if the temp file exists before trying to remove it.
  if [ -f /tmp/cloudflared.deb ]; then
    step "Cleaning up temporary files..."
    rm -f /tmp/cloudflared.deb
    info "Cleanup complete."
  fi
}
trap cleanup EXIT


# --- Main Script ---
ensure_root

# Banner and confirmation
info "=== DNS-over-HTTPS (DoH) Installer ==="
info "This script will install cloudflared and configure your system to use DNS-over-HTTPS."

read -p $'\033[1;33m       Proceed with installation? [y/N]: \033[0m' confirm
if [[ ! "$confirm" =~ ^[Yy] ]]; then
  error "Aborted by user."
  exit 0
fi

# Ask for DoH upstream
UPSTREAM="$DEFAULT_UPSTREAM"
read -p $'\033[1;33m       Use default Cloudflare DoH upstream? [Y/n]: \033[0m' use_default
if [[ "$use_default" =~ ^[Nn] ]]; then
  read -p $'\033[1;33m       Enter custom DoH URL: \033[0m' custom_url
  if [ -n "$custom_url" ]; then
    UPSTREAM="$custom_url"
  else
    warn "No custom URL entered. Using default."
  fi
fi
info "Using DoH upstream: $UPSTREAM"


# --- Dependency Installation ---

step "Checking for existing cloudflared installation..."
if ! command -v cloudflared &> /dev/null; then
    info "cloudflared not found. Proceeding with installation."
    step "Updating package index..."
    apt-get update -y &>/dev/null || true

    step "Downloading the latest cloudflared package..."
    wget --show-progress --progress=bar:force:noscroll -O /tmp/cloudflared.deb \
      https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb \
      || fatal "Download failed. Check your internet connection or permissions to write to /tmp."
    info "Download complete."

    step "Installing cloudflared..."
    dpkg -i /tmp/cloudflared.deb || apt-get install -f -y
    info "cloudflared installed successfully."

    step "Verifying new installation..."
    cloudflared --version
else
    info "cloudflared is already installed. Skipping installation."
    step "Verifying existing installation..."
    cloudflared --version
fi

# --- Service Configuration ---

step "Creating service user 'cloudflared'..."
if ! id cloudflared &>/dev/null; then
  useradd -r -s /usr/sbin/nologin cloudflared
  info "User 'cloudflared' created."
else
  info "User 'cloudflared' already exists."
fi

step "Creating systemd service file..."
cat > /etc/systemd/system/cloudflared.service <<EOF
[Unit]
Description=cloudflared DNS over HTTPS proxy
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=10

[Service]
# Service execution
Type=simple
User=cloudflared
ExecStart=/usr/bin/cloudflared proxy-dns --port 53 --address 127.0.0.1 --upstream ${UPSTREAM}
TimeoutStopSec=20
Restart=on-failure
RestartSec=5s

# User and group configuration
User=cloudflared
Group=cloudflared

# Capability controls: Limit process abilities
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
AmbientCapabilities=CAP_NET_BIND_SERVICE
NoNewPrivileges=true

# Filesystem sandboxing: Restrict file access
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
PrivateDevices=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true

# System call and resource controls: Restrict kernel interactions
MemoryDenyWriteExecute=true
RestrictAddressFamilies=AF_INET AF_INET6
RestrictNamespaces=true
SystemCallArchitectures=native

# Resource limits
LimitNOFILE=1024
LimitNPROC=10

[Install]
WantedBy=multi-user.target
EOF
info "Service file created at /etc/systemd/system/cloudflared.service"

step "Granting permissions for privileged port 53..."
setcap 'cap_net_bind_service=+ep' /usr/bin/cloudflared
info "Permissions granted for port 53."

step "Enabling and starting cloudflared service..."
systemctl daemon-reload
systemctl enable cloudflared
systemctl restart cloudflared
info "cloudflared service has been enabled and started."


# --- System DNS Configuration ---

step "Disabling systemd-resolved to prevent conflicts..."
if systemctl list-unit-files | grep -q 'systemd-resolved.service'; then
  if systemctl is-active --quiet systemd-resolved; then
    systemctl stop systemd-resolved
    info "systemd-resolved service stopped."
  else
    warn "systemd-resolved service was not running."
  fi
  systemctl disable systemd-resolved &>/dev/null || true
  info "systemd-resolved service disabled."
else
  warn "systemd-resolved service not found, skipping."
fi

step "Configuring /etc/resolv.conf to use local cloudflared..."
# Make the file mutable first in case it was set to immutable
chattr -i /etc/resolv.conf 2>/dev/null || true
# Overwrite resolv.conf to point to the local DoH proxy
echo "nameserver 127.0.0.1" > /etc/resolv.conf
info "/etc/resolv.conf now points to 127.0.0.1"


# --- Tailscale Integration ---
step "Checking for active Tailscale instance..."
if command -v tailscale &> /dev/null && tailscale status &>/dev/null; then
    info "Active Tailscale instance detected."
    step "Reconnecting Tailscale without overriding DNS..."
    tailscale up --accept-dns=false
    info "Tailscale reconnected. MagicDNS will work, but system DNS remains with cloudflared."
else
    info "No active Tailscale instance found. Skipping integration."
fi


# --- Finalization ---
step "Setting up auto-restart on network changes..."
if ! dpkg -s networkd-dispatcher &>/dev/null; then
    apt-get install -y networkd-dispatcher &>/dev/null
fi
mkdir -p /etc/networkd-dispatcher/routable.d
cat > /etc/networkd-dispatcher/routable.d/50-restart-cloudflared.sh <<'EOF'
#!/bin/sh
# This script restarts cloudflared whenever the network status becomes "routable".
systemctl restart cloudflared
EOF
chmod +x /etc/networkd-dispatcher/routable.d/50-restart-cloudflared.sh
systemctl restart networkd-dispatcher &>/dev/null || true
info "networkd-dispatcher configured to restart cloudflared."

echo
info "✅ DNS-over-HTTPS setup is complete!"
info "Your system DNS is now set to use DoH via 127.0.0.1."
info "To verify, run: dig google.com @127.0.0.1"
echo
