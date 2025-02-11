# DoH Switcher

A Python-based Terminal User Interface (TUI) tool to manage and switch between various DNS over HTTPS (DoH) providers for the `cloudflared` service. This script allows users to select predefined DoH providers, input custom DoH URLs, persist custom entries for future use, and toggle file permissions for the `cloudflared` service files.

## Features

- **Predefined DoH Providers**: Choose from a list of popular DoH providers.
- **Persistent Custom DoH Entries**: Input a custom DoH URL along with a provider name, which will be saved for future use.
- **File Permission Management**: Toggle file permissions between `600` and `666` for `/etc/systemd/system/cloudflared.service` and its backup.
- **Automatic Configuration Update**: Updates `cloudflared.service` with the selected DoH provider and restarts the service.

## Prerequisites

- Python 3.x
- `cloudflared` installed and configured as per the guide: [Setting Up DNS over HTTPS (DoH) Using cloudflared](https://gist.github.com/1999AZZAR/d5b9207aaa3302dc7fa9bab1fa4fb80f)

## Installation

1. **Clone the Repository**:
   
   ```bash
   git clone https://github.com/1999AZZAR/doh-switcher.git
   cd doh-switcher
   ```

2. **Make the Script Executable**:
   
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
- **Toggle File Permissions**: Press `t` to switch between `600` and `666` permissions for the service files.
- **Exit**: Press `q` to quit the application.

## Important Notes

- Ensure that the `cloudflared` service is properly installed and configured as per the [provided guide](https://gist.github.com/1999AZZAR/d5b9207aaa3302dc7fa9bab1fa4fb80f).
- Running the script with `sudo` is necessary to modify system files and restart services.
- Custom DoH entries are stored in `doh_providers.json` and will persist across sessions.
- Always verify the integrity and source of custom DoH URLs before usage.
