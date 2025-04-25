#!/usr/bin/env bash
set -e

# This script uninstalls and reverts DNS over HTTPS (DoH) setup by cloudflared
# Usage: sudo ./uninstall.sh

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
  error "Please run as root or with sudo"
  exit 1
fi

# Confirmation
info "=== DNS-over-HTTPS (DoH) Uninstaller ==="
read -p $'\033[1;33mProceed with uninstallation? [y/N]: \033[0m' confirm
if [[ ! "$confirm" =~ ^[Yy] ]]; then
  error "Aborted by user."
  exit 1
fi

step "Stopping cloudflared service..."
systemctl stop cloudflared

step "Disabling cloudflared service..."
systemctl disable cloudflared 2>/dev/null || true

step "Removing cloudflared service file..."
rm -f /etc/systemd/system/cloudflared.service

step "Reloading systemd daemon..."
systemctl daemon-reload

step "Removing cloudflared package..."
apt-get remove --purge -y cloudflared || warn "Package cloudflared not installed"
apt-get autoremove -y

step "Removing service user..."
if id cloudflared &>/dev/null; then
  userdel cloudflared
  info "Service user removed"
else
  warn "Service user not found"
fi

step "Revoking port binding permissions..."
setcap -r /usr/bin/cloudflared 2>/dev/null || true

step "Removing firewall rules..."
iptables -D INPUT -p tcp --dport 53 -j ACCEPT 2>/dev/null || true
iptables -D INPUT -p udp --dport 53 -j ACCEPT 2>/dev/null || true

step "Removing networkd-dispatcher hook..."
rm -f /etc/networkd-dispatcher/routable.d/restart-cloudflared.sh 2>/dev/null || true

step "Restoring DNS resolver..."
systemctl enable systemd-resolved || true
systemctl start systemd-resolved || true
rm -f /etc/resolv.conf
ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf

info "Uninstallation complete. Verify internet with: ping -c1 google.com"
