#!/usr/bin/env bash

# This script uninstalls and reverts DNS over HTTPS (DoH) setup by cloudflared
# Usage: sudo ./uninstall.sh

# ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Global variables
SCRIPT_LOG="/tmp/doh_uninstall.log"
ERRORS_ENCOUNTERED=0
WARNINGS_ENCOUNTERED=0

# Logging functions
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') - $*" >> "$SCRIPT_LOG"; }
step() { echo -e "${BLUE}[STEP]${NC} $*"; log "STEP: $*"; }
info() { echo -e "${GREEN}[OK]${NC} $*"; log "OK: $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; log "WARN: $*"; ((WARNINGS_ENCOUNTERED++)); }
error() { echo -e "${RED}[ERROR]${NC} $*"; log "ERROR: $*"; ((ERRORS_ENCOUNTERED++)); }

# Execute command with error handling
safe_exec() {
    local cmd="$1"
    local description="$2"
    local critical="${3:-false}"

    log "Executing: $cmd"

    if eval "$cmd" >> "$SCRIPT_LOG" 2>&1; then
        info "$description - Success"
        return 0
    else
        local exit_code=$?
        if [ "$critical" = "true" ]; then
            error "$description - Failed (exit code: $exit_code) - This is critical"
            return $exit_code
        else
            warn "$description - Failed (exit code: $exit_code) - Continuing anyway"
            return 0
        fi
    fi
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if service exists
service_exists() {
    systemctl list-unit-files --type=service | grep -q "^$1.service"
}

# Check if user exists
user_exists() {
    id "$1" &>/dev/null
}

# Check if file exists and remove it
safe_remove() {
    local file="$1"
    local description="$2"

    if [ -f "$file" ] || [ -L "$file" ]; then
        safe_exec "rm -f '$file'" "$description"
    else
        info "$description - File not found, skipping"
    fi
}

# Backup function
create_backup() {
    local file="$1"
    local backup_dir="/tmp/doh_uninstall_backup_$(date +%Y%m%d_%H%M%S)"

    if [ -f "$file" ]; then
        mkdir -p "$backup_dir"
        cp "$file" "$backup_dir/" 2>/dev/null && info "Backed up $file to $backup_dir"
    fi
}

# Ensure running as root
if [ "$(id -u)" -ne 0 ]; then
    error "Please run as root or with sudo"
    exit 1
fi

# Initialize log
echo "=== DoH Uninstall Log Started at $(date) ===" > "$SCRIPT_LOG"

# Confirmation
info "=== DNS-over-HTTPS (DoH) Robust Uninstaller ==="
info "Log file: $SCRIPT_LOG"
echo
read -p $'\033[1;33mProceed with uninstallation? [y/N]: \033[0m' confirm
if [[ ! "$confirm" =~ ^[Yy] ]]; then
    error "Aborted by user."
    exit 1
fi

echo
step "Starting uninstallation process..."

# Step 1: Stop cloudflared service
step "1/12 Stopping cloudflared service..."
if service_exists "cloudflared"; then
    safe_exec "systemctl stop cloudflared" "Stop cloudflared service"
    # Give it time to stop gracefully
    sleep 2
    # Force kill if still running
    if pgrep cloudflared >/dev/null; then
        safe_exec "pkill -f cloudflared" "Force kill cloudflared processes"
        sleep 1
    fi
else
    info "Cloudflared service not found, skipping"
fi

# Step 2: Disable cloudflared service
step "2/12 Disabling cloudflared service..."
if service_exists "cloudflared"; then
    safe_exec "systemctl disable cloudflared" "Disable cloudflared service"
else
    info "Cloudflared service not found, skipping"
fi

# Step 3: Remove cloudflared service file
step "3/12 Removing cloudflared service file..."
create_backup "/etc/systemd/system/cloudflared.service"
safe_remove "/etc/systemd/system/cloudflared.service" "Remove service file"

# Step 4: Reload systemd daemon
step "4/12 Reloading systemd daemon..."
safe_exec "systemctl daemon-reload" "Reload systemd daemon" "true"

# Step 5: Remove cloudflared package
step "5/12 Removing cloudflared package..."
if command_exists "apt-get"; then
    # Check if package is installed
    if dpkg -l | grep -q cloudflared; then
        safe_exec "apt-get remove --purge -y cloudflared" "Remove cloudflared package"
        safe_exec "apt-get autoremove -y" "Remove unused dependencies"
    else
        info "Cloudflared package not installed via apt"
    fi
elif command_exists "yum"; then
    if yum list installed cloudflared &>/dev/null; then
        safe_exec "yum remove -y cloudflared" "Remove cloudflared package (yum)"
    else
        info "Cloudflared package not installed via yum"
    fi
elif command_exists "dnf"; then
    if dnf list installed cloudflared &>/dev/null; then
        safe_exec "dnf remove -y cloudflared" "Remove cloudflared package (dnf)"
    else
        info "Cloudflared package not installed via dnf"
    fi
else
    warn "No supported package manager found"
fi

# Remove manually installed binary if it exists
if [ -f "/usr/bin/cloudflared" ]; then
    safe_remove "/usr/bin/cloudflared" "Remove cloudflared binary"
fi

if [ -f "/usr/local/bin/cloudflared" ]; then
    safe_remove "/usr/local/bin/cloudflared" "Remove cloudflared binary (local)"
fi

# Step 6: Remove service user
step "6/12 Removing service user..."
if user_exists "cloudflared"; then
    safe_exec "userdel cloudflared" "Remove cloudflared user"
else
    info "Service user not found, skipping"
fi

# Step 7: Remove group if it exists
if getent group cloudflared >/dev/null 2>&1; then
    safe_exec "groupdel cloudflared" "Remove cloudflared group"
else
    info "Cloudflared group not found, skipping"
fi

# Step 8: Revoke port binding permissions
step "7/12 Revoking port binding permissions..."
for binary in "/usr/bin/cloudflared" "/usr/local/bin/cloudflared"; do
    if [ -f "$binary" ]; then
        safe_exec "setcap -r '$binary'" "Remove capabilities from $binary"
    fi
done

# Step 9: Remove firewall rules (multiple firewall systems)
step "8/12 Removing firewall rules..."

# iptables
if command_exists "iptables"; then
    safe_exec "iptables -D INPUT -p tcp --dport 53 -j ACCEPT" "Remove iptables TCP rule"
    safe_exec "iptables -D INPUT -p udp --dport 53 -j ACCEPT" "Remove iptables UDP rule"
    safe_exec "iptables -D INPUT -p tcp --dport 5053 -j ACCEPT" "Remove iptables TCP 5053 rule"
    safe_exec "iptables -D INPUT -p udp --dport 5053 -j ACCEPT" "Remove iptables UDP 5053 rule"
fi

# ufw
if command_exists "ufw"; then
    safe_exec "ufw delete allow 53" "Remove ufw DNS rule"
    safe_exec "ufw delete allow 5053" "Remove ufw 5053 rule"
fi

# firewalld
if command_exists "firewall-cmd"; then
    safe_exec "firewall-cmd --permanent --remove-port=53/tcp" "Remove firewalld TCP rule"
    safe_exec "firewall-cmd --permanent --remove-port=53/udp" "Remove firewalld UDP rule"
    safe_exec "firewall-cmd --permanent --remove-port=5053/tcp" "Remove firewalld TCP 5053 rule"
    safe_exec "firewall-cmd --permanent --remove-port=5053/udp" "Remove firewalld UDP 5053 rule"
    safe_exec "firewall-cmd --reload" "Reload firewalld"
fi

# Step 10: Remove configuration files and directories
step "9/12 Removing configuration files..."
safe_remove "/etc/default/cloudflared" "Remove cloudflared defaults"
safe_remove "/etc/cloudflared/cloudflared.yml" "Remove cloudflared config"
safe_exec "rmdir /etc/cloudflared" "Remove cloudflared config directory"

# Remove any leftover files
for file in /etc/cloudflared*; do
    if [ -e "$file" ]; then
        safe_remove "$file" "Remove leftover config file: $file"
    fi
done

# Step 11: Remove networkd-dispatcher hook
step "10/12 Removing networkd-dispatcher hook..."
safe_remove "/etc/networkd-dispatcher/routable.d/restart-cloudflared.sh" "Remove networkd dispatcher hook"

# Remove other potential hook locations
safe_remove "/etc/network/if-up.d/cloudflared" "Remove network if-up hook"
safe_remove "/etc/dhcp/dhclient-exit-hooks.d/cloudflared" "Remove DHCP hook"

# Step 12: Restore DNS resolver
step "11/12 Restoring DNS resolver..."

# Backup current resolv.conf
create_backup "/etc/resolv.conf"

# Try to restore systemd-resolved
if command_exists "systemctl"; then
    safe_exec "systemctl enable systemd-resolved" "Enable systemd-resolved"
    safe_exec "systemctl start systemd-resolved" "Start systemd-resolved"

    # Wait for systemd-resolved to start
    sleep 3

    if [ -f "/run/systemd/resolve/stub-resolv.conf" ]; then
        safe_exec "rm -f /etc/resolv.conf" "Remove current resolv.conf"
        safe_exec "ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf" "Link systemd-resolved stub"
    elif [ -f "/run/systemd/resolve/resolv.conf" ]; then
        safe_exec "rm -f /etc/resolv.conf" "Remove current resolv.conf"
        safe_exec "ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf" "Link systemd-resolved"
    else
        warn "systemd-resolved files not found, creating fallback resolv.conf"
        cat > /etc/resolv.conf << 'EOF'
# Fallback DNS configuration
nameserver 8.8.8.8
nameserver 8.8.4.4
nameserver 1.1.1.1
EOF
    fi
else
    # Fallback for systems without systemctl
    warn "systemctl not found, creating fallback DNS configuration"
    cat > /etc/resolv.conf << 'EOF'
# Fallback DNS configuration
nameserver 8.8.8.8
nameserver 8.8.4.4
nameserver 1.1.1.1
EOF
fi

# Step 13: Final cleanup and testing
step "12/12 Final cleanup and testing..."

# Remove any remaining processes
if pgrep -f cloudflared >/dev/null; then
    safe_exec "pkill -9 -f cloudflared" "Force kill remaining cloudflared processes"
fi

# Clear DNS cache if possible
if command_exists "systemd-resolve"; then
    safe_exec "systemd-resolve --flush-caches" "Flush DNS cache"
elif command_exists "resolvectl"; then
    safe_exec "resolvectl flush-caches" "Flush DNS cache (resolvectl)"
fi

# Test DNS resolution
step "Testing DNS resolution..."
if ping -c1 -W5 google.com >/dev/null 2>&1; then
    info "DNS resolution test: SUCCESS"
elif ping -c1 -W5 8.8.8.8 >/dev/null 2>&1; then
    info "Network connectivity: OK, DNS may need time to propagate"
else
    warn "Network connectivity test failed - please check your network"
fi

# Summary
echo
info "=== Uninstallation Summary ==="
info "Errors encountered: $ERRORS_ENCOUNTERED"
info "Warnings encountered: $WARNINGS_ENCOUNTERED"
info "Log file saved to: $SCRIPT_LOG"

if [ $ERRORS_ENCOUNTERED -eq 0 ]; then
    info "✅ Uninstallation completed successfully!"
    info "Your system should now use the default DNS resolver."
    info "You may need to restart network services or reboot for all changes to take effect."
else
    warn "⚠️  Uninstallation completed with $ERRORS_ENCOUNTERED errors."
    warn "Please check the log file for details: $SCRIPT_LOG"
fi

echo
info "Recommended next steps:"
info "1. Test internet connectivity: ping -c3 google.com"
info "2. Check DNS resolution: nslookup google.com"
info "3. Restart networking if needed: systemctl restart networking"
info "4. Reboot system if problems persist"

exit 0
