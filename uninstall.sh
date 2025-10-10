#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# Colors for TUI
NC='\e[0m'
RED='\e[31m'
GREEN='\e[32m'
YELLOW='\e[33m'
BLUE='\e[34m'

# Parse CLI options
SKIP_CONFIRM=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    -y|--yes) SKIP_CONFIRM=true; shift;;
    -h|--help) echo "Usage: $0 [-y|--yes]"; exit 0;;
    *) break;;
  esac
done

# Ensure running as root
if [[ $EUID -ne 0 ]]; then
  echo -e "${RED}Please run as root or via sudo.${NC}"
  exit 1
fi

clear
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   DoH Switcher Uninstaller v1.0   ${NC}"
echo -e "${BLUE}========================================${NC}"
echo

if ! $SKIP_CONFIRM; then
  echo -ne "${YELLOW}Proceed with uninstallation? (y/N):${NC} "
  read confirm
  [[ $confirm != [yY] ]] && echo -e "${RED}Uninstallation aborted.${NC}" && exit 1
fi

# Core script settings
CORE_SCRIPT_DEST_NAME="doh-switcher-core"
CORE_BIN_PATH="/usr/local/bin/${CORE_SCRIPT_DEST_NAME}"
DEFAULT_LOG_FILE="/var/log/doh-switcher.log"

# Web UI service settings
WEBUI_SERVICE_NAME="doh-switcher"
WEBUI_SERVICE_FILE="/etc/systemd/system/${WEBUI_SERVICE_NAME}.service"
WEBUI_APP_DIR="/opt/${WEBUI_SERVICE_NAME}"

# Stop any running Web UI processes (Step 1/7)
echo -e "${YELLOW}[1/7] Stopping any running Web UI processes...${NC}"
sudo pkill -f "${WEBUI_APP_DIR}/app.py" || true
echo -e "${GREEN}[OK] Web UI processes stopped${NC}"

# Stop and disable the service (Step 2/7)
echo -e "${YELLOW}[2/7] Stopping and disabling ${WEBUI_SERVICE_NAME} service...${NC}"
sudo systemctl stop "$WEBUI_SERVICE_NAME" || true
sudo systemctl disable "$WEBUI_SERVICE_NAME" || true
echo -e "${GREEN}[OK] Service stopped and disabled${NC}"

# Remove systemd unit and reload (Step 3/7)
echo -e "${YELLOW}[3/7] Removing service file at ${WEBUI_SERVICE_FILE}...${NC}"
sudo rm -f "$WEBUI_SERVICE_FILE"
sudo systemctl daemon-reload
echo -e "${GREEN}[OK] Service unit removed${NC}"

# Remove application directory (Step 4/7)
echo -e "${YELLOW}[4/7] Removing application directory ${WEBUI_APP_DIR}...${NC}"
sudo rm -rf "$WEBUI_APP_DIR"
echo -e "${GREEN}[OK] Application directory removed${NC}"

# Remove core script (Step 5/7)
echo -e "${YELLOW}[5/7] Removing core script at ${CORE_BIN_PATH}...${NC}"
sudo rm -f "$CORE_BIN_PATH"
echo -e "${GREEN}[OK] Core script removed${NC}"

# Remove log file (Step 6/7)
echo -e "${YELLOW}[6/7] Removing log file at ${DEFAULT_LOG_FILE}...${NC}"
sudo rm -f "$DEFAULT_LOG_FILE"
echo -e "${GREEN}[OK] Log file removed${NC}"

# Remove alias from user shell config
TARGET_USER=${SUDO_USER:-$USER}
TARGET_HOME=$(eval echo "~${TARGET_USER}")
TARGET_SHELL=$(getent passwd "$TARGET_USER" | cut -d: -f7)
case "$TARGET_SHELL" in
  */bash) RC_FILE="$TARGET_HOME/.bashrc" ;;
  */zsh)  RC_FILE="$TARGET_HOME/.zshrc"  ;;
  *)      RC_FILE="$TARGET_HOME/.profile" ;;
esac

# Remove alias (Step 7/7)
echo -e "${YELLOW}[7/7] Removing alias 'cdns' from ${RC_FILE}...${NC}"
# Use '#' as sed delimiter to avoid escaping slashes
sudo sed -i "\#alias cdns='${CORE_BIN_PATH}'#d" "$RC_FILE"
echo -e "${GREEN}[OK] Alias removed${NC}"

echo -e "${BLUE}Uninstallation finished!${NC}"
