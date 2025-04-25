#!/usr/bin/env bash
# Exit on error
set -e

# Colors for TUI
NC='\e[0m'
RED='\e[31m'
GREEN='\e[32m'
YELLOW='\e[33m'
BLUE='\e[34m'

# Check for prerequisites (Cloudflared)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v cloudflared >/dev/null; then
  echo -e "${YELLOW}Prerequisites missing: cloudflared not found. Installing prerequisites...${NC}"
  sudo bash "${SCRIPT_DIR}/Prerequisites/install.sh"
fi

# Clear and show banner
clear
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   DoH Switcher Installer v1.0   ${NC}"
echo -e "${BLUE}========================================${NC}"
echo

# Prompt to confirm installation
echo -ne "${YELLOW}Proceed with installation? (y/N):${NC} "
read confirm
[[ $confirm != [yY] ]] && echo -e "${RED}Installation aborted.${NC}" && exit 1

# Core script install
CORE_SCRIPT_DEST_NAME="doh-switcher-core"  # override if needed
CORE_BIN_PATH="/usr/local/bin/${CORE_SCRIPT_DEST_NAME}"
DEFAULT_LOG_FILE="/var/log/doh-switcher.log"

# Web UI service settings
WEBUI_SERVICE_NAME="doh-switcher"
WEBUI_APP_DIR="/opt/${WEBUI_SERVICE_NAME}"
WEBUI_SERVICE_FILE="/etc/systemd/system/${WEBUI_SERVICE_NAME}.service"
WEBUI_SOURCE_DIR_NAME="."  # adjust if your source is in a subdir like 'webui'
WEBUI_VENV_PATH="${WEBUI_APP_DIR}/venv"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${YELLOW}[1/7] Installing core script to ${CORE_BIN_PATH}...${NC}"
sudo install -m 0755 "${SCRIPT_DIR}/change_dns.sh" "${CORE_BIN_PATH}"
echo -e "${GREEN}[OK] Core script installed${NC}"

echo -e "${YELLOW}[2/7] Creating log file at ${DEFAULT_LOG_FILE}...${NC}"
sudo mkdir -p "$(dirname "${DEFAULT_LOG_FILE}")"
sudo touch "${DEFAULT_LOG_FILE}"
sudo chmod 644 "${DEFAULT_LOG_FILE}"
echo -e "${GREEN}[OK] Log file ready${NC}"

echo -e "${YELLOW}[3/7] Setting up web UI in ${WEBUI_APP_DIR}...${NC}"
sudo mkdir -p "${WEBUI_APP_DIR}"
sudo cp -r "${SCRIPT_DIR}/${WEBUI_SOURCE_DIR_NAME}/." "${WEBUI_APP_DIR}/"
echo -e "${GREEN}[OK] Web UI files copied${NC}"

echo -e "${YELLOW}[4/7] Creating Python venv at ${WEBUI_VENV_PATH}...${NC}"
sudo python3 -m venv "${WEBUI_VENV_PATH}"
sudo "${WEBUI_VENV_PATH}/bin/pip" install --upgrade pip
sudo "${WEBUI_VENV_PATH}/bin/pip" install -r "${WEBUI_APP_DIR}/requirements.txt"
echo -e "${GREEN}[OK] Virtualenv and dependencies installed${NC}"

echo -e "${YELLOW}[5/7] Writing systemd service file to ${WEBUI_SERVICE_FILE}...${NC}"
sudo tee "${WEBUI_SERVICE_FILE}" > /dev/null <<EOF
[Unit]
Description=DoH Switcher Web UI
After=network.target

[Service]
Type=simple
WorkingDirectory=${WEBUI_APP_DIR}
ExecStart=${WEBUI_VENV_PATH}/bin/python ${WEBUI_APP_DIR}/app.py
Restart=on-failure
StandardOutput=append:${DEFAULT_LOG_FILE}
StandardError=append:${DEFAULT_LOG_FILE}

[Install]
WantedBy=multi-user.target
EOF
echo -e "${GREEN}[OK] Service file created${NC}"

echo -e "${YELLOW}[6/7] Reloading systemd, enabling and starting the service...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable "${WEBUI_SERVICE_NAME}"
sudo systemctl start "${WEBUI_SERVICE_NAME}"
echo -e "${GREEN}[OK] Service is up and running${NC}"

echo -e "${GREEN}All steps completed!${NC}"

# Determine alias insertion for target user
TARGET_USER=${SUDO_USER:-$USER}
TARGET_HOME=$(eval echo "~$TARGET_USER")
TARGET_SHELL=$(getent passwd "$TARGET_USER" | cut -d: -f7)
if [[ "${TARGET_SHELL}" == */bash ]]; then RC_FILE="${TARGET_HOME}/.bashrc"; elif [[ "${TARGET_SHELL}" == */zsh ]]; then RC_FILE="${TARGET_HOME}/.zshrc"; else RC_FILE="${TARGET_HOME}/.profile"; fi
echo -e "${YELLOW}[7/7] Adding alias 'cdns' to ${RC_FILE}...${NC}"
ALIAS_CMD="alias cdns='${CORE_BIN_PATH}'"
sudo grep -qxF "${ALIAS_CMD}" "${RC_FILE}" || sudo bash -c "echo '${ALIAS_CMD}' >> '${RC_FILE}'"
echo -e "${GREEN}[OK] Alias 'cdns' added to ${RC_FILE}${NC}"
echo -e "${BLUE}Installation finished! Run 'source ${RC_FILE}' or open a new shell to start using 'cdns'.${NC}"
