# DoH Switcher

A modern, web-based interface to manage and switch between DNS over HTTPS (DoH) providers for your system. DoH Switcher allows you to easily select, test, and manage your DNS over HTTPS providers through an intuitive interface.

![DoH Switcher](screenshot.png)

## Overview

DoH Switcher is a Flask-based web application that helps you manage the DNS over HTTPS service running on your system. It works with Cloudflared as the DoH proxy service and allows you to:

- Switch between different DoH providers with a single click
- Test and compare latency between providers
- Add custom DoH providers
- Backup and restore your configuration
- Monitor service status

## Prerequisites

The `install.sh` script will automatically check for Cloudflared and install it if missing. You can run:

```bash
sudo ./install.sh
```

to install all required components.

If you prefer to install prerequisites manually, see the [Prerequisites guide](Prerequisites/README.md) in the Prerequisites folder.

## Installation

1. Clone this repository and enter the directory:
   ```bash
   git clone https://github.com/1999AZZAR/doh-switcher.git
   cd doh-switcher
   ```

2. Run the installer script:
   ```bash
   sudo ./install.sh
   ```
   This will:
   - Install the `cdns` alias
   - Create a Python virtual environment and install dependencies
   - Set up and start the systemd service
   - Add the `cdns` alias to your shell configuration

3. Reload your shell configuration:
   ```bash
   source ~/.bashrc  # or ~/.zshrc, ~/.profile
   ```

4. Launch the Web UI:
   ```bash
   cdns
   ```
   This will silently start the service and open your browser.

### Uninstallation

To remove DoH Switcher and clean up all components, run:
```bash
sudo ./uninstall.sh
```
This will:
  - Stop any running Web UI processes and the systemd service
  - Remove the service unit, application files, logs, and alias

## Features

### Service Controls

- **Backup Config**: Save your current DoH providers configuration
- **Restore Config**: Restore a previously saved configuration
- **Test All Providers**: Measure latency and connectivity of all providers at once

### DoH Provider Management

- **View Current Provider**: See which DoH provider is currently active
- **Service Status Monitoring**: Check if the Cloudflared service is running
- **Switch Providers**: Change your DoH provider with a single click
- **Test Individual Providers**: Check the performance of specific providers
- **Add Custom Providers**: Add your own DoH provider endpoints
- **Delete Custom Providers**: Remove custom providers you no longer need

### Performance Testing

The application performs one type of test:

- **Ping Test**: Basic connectivity test to the provider's host

## Default Providers

The application comes with these pre-configured providers:

- Cloudflare (`https://cloudflare-dns.com/dns-query`)
- Google (`https://dns.google/dns-query`)
- Quad9 (`https://dns.quad9.net/dns-query`)
- NextDNS (`https://dns.nextdns.io`)
- AdGuard (`https://dns.adguard.com/dns-query`)

## Adding Custom Providers

To add a custom DoH provider:

1. Enter the provider name in the "Provider Name" field
2. Enter the DoH URL in the "DoH URL" field
3. Click "Add Provider"

The application will validate the DoH URL before adding it to ensure it's a valid DNS over HTTPS endpoint.

## Technical Details

### How it works

DoH Switcher manages the Cloudflared service by:

1. Modifying the systemd service file located at `/etc/systemd/system/cloudflared.service`
2. Updating the `--upstream` parameter to point to your selected DoH provider
3. Reloading the systemd daemon and restarting the service

### File Structure

- `app.py`: Main Flask application and backend logic
- `templates/index.html`: Web interface template
- `static/css/styles.css`: CSS styling for the web interface
- `doh_providers.json`: Saved DoH providers configuration
- `doh_providers_backup.json`: Backup of the configuration

### Logging

The application logs all actions to `doh_manager.log` for troubleshooting and auditing purposes.

## Troubleshooting

### Service Not Running

If the service status shows "not running":

1. Check the Cloudflared service manually: `sudo systemctl status cloudflared`
2. Check logs: `sudo journalctl -u cloudflared`
3. Ensure prerequisites are installed: run `sudo ./install.sh` (it will install Cloudflared if needed), or consult the [Prerequisites guide](Prerequisites/README.md)
4. Try restarting the service: `sudo systemctl restart cloudflared`

### Failed Tests

If providers show "Failed" in testing:

1. Check your internet connection
2. Verify the DoH provider is operational
3. Ensure there's no firewall blocking the connection

### Permission Issues

The application requires root privileges to modify system service files. Always run with:

```bash
sudo python app.py
```

## Security Considerations

- The application requires root privileges to modify systemd service files
- All provider URLs are validated before use
- The web interface is only accessible from localhost by default
- Consider setting up basic authentication if exposing to a network

## License

[MIT License](LICENSE)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- This project relies on Cloudflared by Cloudflare
- Thanks to all the public DoH providers for their services

---

**Note:** The installer automatically handles Cloudflared setup. Run `sudo ./install.sh`, or see the [Prerequisites guide](Prerequisites/README.md) for manual installation steps.
