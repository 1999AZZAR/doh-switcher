# DoH Switcher

A Python-based Terminal User Interface (TUI) tool to manage and switch between various DNS over HTTPS (DoH) providers for the `cloudflared` service. This script allows users to select predefined DoH providers, input custom DoH URLs, persist custom entries for future use, and toggle file permissions for the `cloudflared` service files.

## Features

- **Predefined DoH Providers**: Choose from a list of popular DoH providers.
- **Persistent Custom DoH Entries**: Input a custom DoH URL along with a provider name, which will be saved for future use.
- **File Permission Management**: Toggle file permissions between `600` and `666` for `/etc/systemd/system/cloudflared.service` and its backup.
- **Automatic Configuration Update**: Updates `cloudflared.service` with the selected DoH provider and restarts the service.
- **Cancel Mechanism**: Cancel actions (e.g., adding a custom provider) by pressing `q`.
- **Clear Terminal on Input**: The terminal screen is cleared before displaying the menu or any new output for a clean interface.
- **Backup and Restore Configuration**: Backup your DoH provider configuration to a file and restore it later.
- **Service Status Check**: Check if the `cloudflared` service is running.
- **Interactive Help Menu**: Display a help menu with instructions for using the tool.
- **Logging**: Logs important events (e.g., provider changes, permission changes) for debugging and auditing.

## Prerequisites

- Python 3.x
- `cloudflared` installed and configured as per the guide: [Setting Up DNS over HTTPS (DoH) Using cloudflared](https://gist.github.com/1999AZZAR/d5b9207aaa3302dc7fa9bab1fa4fb80f)

## Installation

1. **Clone the Repository**:

   ```bash
   git clone https://github.com/1999AZZAR/doh-switcher.git
   cd doh-switcher
   ```

2. **Install Required Python Packages**:

   ```bash
   pip install requests colorama
   ```

3. **Make the Script Executable**:

   ```bash
   chmod +x switcher.py
   ```

## Usage

Run the script with elevated privileges to modify system files and manage services:

```bash
sudo python switcher.py
```

Upon running, you'll be presented with a menu:

- **Predefined DoH Providers**: Select by entering the corresponding number.
- **Custom DoH Provider**: Press `c`, enter a provider name and custom URL. The entry will be saved for future use.
- **Delete Custom Provider**: Press `d` to delete a custom provider from the list.
- **Toggle File Permissions**: Press `t` to switch between `600` and `666` permissions for the service files.
- **Backup Configuration**: Press `b` to backup your DoH provider configuration to a file.
- **Restore Configuration**: Press `r` to restore your DoH provider configuration from a backup file.
- **Check Service Status**: Press `s` to check if the `cloudflared` service is running.
- **Help**: Press `h` to display the help menu.
- **Exit**: Press `q` to quit the application.

## Important Notes

- Ensure that the `cloudflared` service is properly installed and configured as per the [provided guide](https://gist.github.com/1999AZZAR/d5b9207aaa3302dc7fa9bab1fa4fb80f).
- Running the script with `sudo` is necessary to modify system files and restart services.
- Custom DoH entries are stored in `doh_providers.json` and will persist across sessions.
- Always verify the integrity and source of custom DoH URLs before usage.
- Logs are stored in `doh_manager.log` for debugging and auditing purposes.

## Example Workflow

1. **Select a Predefined Provider**:
   - Run the script: `sudo python switcher.py`.
   - Enter the number corresponding to the desired provider (e.g., `1` for Cloudflare).

2. **Add a Custom Provider**:
   - Press `c`.
   - Enter a provider name (e.g., `MyCustomDNS`).
   - Enter a custom DoH URL (e.g., `https://mydns.example.com/dns-query`).

3. **Delete a Custom Provider**:
   - Press `d`.
   - Enter the number corresponding to the custom provider you want to delete.

4. **Backup Configuration**:
   - Press `b` to backup your DoH provider configuration to a file.

5. **Restore Configuration**:
   - Press `r` to restore your DoH provider configuration from a backup file.

6. **Check Service Status**:
   - Press `s` to check if the `cloudflared` service is running.

7. **Exit the Application**:
   - Press `q` to quit.
