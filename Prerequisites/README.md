# Cloudflared DNS-over-HTTPS (DoH) Setup & Installer

This guide explains how to set up DNS over HTTPS (DoH) on a Linux system using `cloudflared`. DoH ensures that your DNS queries are encrypted and secure, protecting your online privacy and preventing third-party monitoring of your internet activity.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Prerequisites](#prerequisites)
3. [Step-by-Step Installation and Configuration](#step-by-step-installation-and-configuration)
   - [Automatic Installation](#automatic-installation)
   - [Manual Installation and Setup](#manual-installation-and-setup)
4. [Configure DNS Resolution](#3-configure-dns-resolution)
5. [Verify the Setup](#4-verify-the-setup)
6. [Optional Configuration](#5-optional)
7. [Example DNS over HTTPS (DoH) Providers](#example-dns-over-https-doh-providers)
8. [Conclusion](#conclusion)

## Quick Start

Make the installer and uninstaller executable and run the setup script:

```bash
chmod +x install.sh uninstall.sh
sudo ./install.sh
```

Follow the interactive prompts to select or enter your DoH provider. To uninstall and restore your original DNS settings:

```bash
sudo ./uninstall.sh
```

## Prerequisites

- A Linux-based system (Debian, Ubuntu, etc.).
- `cloudflared` (Cloudflare's DoH proxy) installed.

## Step-by-Step Installation and Configuration

### Automatic Installation

Run **install.sh** to automatically configure DoH:

```bash
chmod +x install.sh uninstall.sh
sudo ./install.sh
```

### Manual Installation and Setup

#### 1. Download and Install cloudflared

1. Download the latest `cloudflared` Debian package:
   
   ```bash
   wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
   ```

2. Install the package:
   
   ```bash
   sudo dpkg -i cloudflared-linux-amd64.deb
   sudo apt-get install -f
   ```

3. Verify the installation:
   
   ```bash
   cloudflared --version
   ```

This installs `cloudflared` and ensures all dependencies are met. You can verify the installation by checking the version with `cloudflared --version`.

#### 2. Set Up DoH Proxy

1. **Create a Service User**
   To run `cloudflared` securely, create a dedicated service user:
   
   ```bash
   sudo useradd -r -s /usr/sbin/nologin cloudflared
   ```
   
   This command creates a system user `cloudflared` with no login permissions.

2. **Configure the Service**
   Create a systemd service file to run `cloudflared` automatically:
   
   ```bash
   sudo nano /etc/systemd/system/cloudflared.service
   ```
   
   Add the following configuration to the service file:
   
   ```ini
   [Unit]
   Description=cloudflared DNS over HTTPS proxy
   After=network-online.target
   Wants=network-online.target
   StartLimitIntervalSec=60
   StartLimitBurst=10
   
   [Service]
   Type=simple
   ExecStart=/usr/bin/cloudflared proxy-dns --port 53 --upstream  <your_DoH>
   User=cloudflared
   Restart=always
   RestartSec=2
   TimeoutStopSec=20
   LimitNOFILE=4096
   
   [Install]
   WantedBy=multi-user.target
   ```
   
   Replace `<your_DoH>` with the URL of your chosen DNS over HTTPS provider (refer to the list below).

3. **Grant Permission to Bind to Port 53**:
   
   On Linux, non-root processes cannot bind to ports below 1024 by default. You can use setcap to allow Cloudflared to bind to port 53 without requiring root privileges:
   
   ```bash
   sudo setcap 'cap_net_bind_service=+ep' /usr/bin/cloudflared
   ```

4. **Reload the systemd daemon and start the service**:
   
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable cloudflared
   sudo systemctl start cloudflared
   ```
   
   This reloads the systemd configuration, enables the `cloudflared` service to start on boot, and starts the service immediately.

### 3. Configure DNS Resolution

To ensure the system uses your DoH proxy for DNS resolution:

1. **Stop and Disable `systemd-resolved`**
   
   The `systemd-resolved` service may conflict with `cloudflared`:
   
   ```bash
   sudo systemctl stop systemd-resolved
   sudo systemctl disable systemd-resolved
   ```

2. **Create a New `/etc/resolv.conf`**
   
   Set up `resolv.conf` to direct DNS queries to `cloudflared`:
   
   ```bash
   sudo rm /etc/resolv.conf
   echo "nameserver 127.0.0.1" | sudo tee /etc/resolv.conf
   ```
   
   This configuration routes DNS queries through `cloudflared` running on localhost.

3. **Configure Firewall**:
   
   If your system uses a firewall, allow traffic on ports 53:
   
   ```bash
   sudo iptables -I INPUT -p tcp --dport 53 -j ACCEPT
   sudo iptables -I INPUT -p udp --dport 53 -j ACCEPT
   ```

### 4. Verify the Setup

To confirm that `cloudflared` is working correctly:

1. **Check if `cloudflared` is Listening on the Correct Ports**
   Run the following commands:
   
   ```bash
   sudo lsof -i :53
   ```
   
   You should see `cloudflared` listed as the service listening on both ports.

2. **Test DNS Resolution**
   Use the `dig` command to test DNS resolution through `cloudflared`:
   
   ```bash
   dig @127.0.0.1 example.com
   ```
   
   The output should show a successful DNS query resolution.

### 5. (optional)

#### Auto-Restart on Network Changes

  setup to restart the cloudflared service whenever the system connects to a new network:

1. **Install `networkd-dispatcher`.**
   
   On Debian-based systems (like Ubuntu), use:
   
   ```bash
   sudo apt update
   sudo apt install networkd-dispatcher
   ```

2. **Create a Script to Restart `cloudflared` on Network Change.**
   
   You need to create a script that networkd-dispatcher will call when a new network connection is detected.
   
   - Create the script:
     
     ```bash
     sudo nano /etc/networkd-dispatcher/routable.d/restart-cloudflared.sh
     ```
   
   - Add the following content to the script:
     
     ```bash
     #!/bin/bash
     
     # Restart the cloudflared service
     systemctl restart cloudflared
     ```
   
   - Make the script executable:
     
     ```bash
     sudo chmod +x /etc/networkd-dispatcher/routable.d/restart-cloudflared.sh
     ```

3. **Reload Systemd and Network Dispatcher.**
   
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart networkd-dispatcher
   sudo systemctl restart cloudflared
   ```
   
   This reloads the systemd configuration, enables the `cloudflared` service to start on boot, and starts the service immediately.

4. **Verify the Configuration.**
   
   - Check the status of the cloudflared service:
   
   ```bash
   sudo systemctl status cloudflared
   ```
   
   - Monitor network events and check if cloudflared restarts when connecting to a new network:
     
     ```bash
     journalctl -u cloudflared -f
     ```

## Example DNS over HTTPS (DoH) Providers

You can choose any of the following DNS providers for your DoH setup:

| Provider              | URL                                                | IPv4                                 | IPv6                                           | Best For                                 | Homepage                                                            | More Info                                                                                        | Pricing                                                                          |
| --------------------- | -------------------------------------------------- | ------------------------------------ | ---------------------------------------------- | ---------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------- |
| **Google Public DNS** | `https://dns.google/dns-query`                     | `8.8.8.8`, `8.8.4.4`                 | `2001:4860:4860::8888`, `2001:4860:4860::8844` | General use, fast global coverage        | [Google Public DNS](https://developers.google.com/speed/public-dns) | No filtering or blocking, focuses on speed and reliability                                       | Free                                                                             |
| **Cloudflare DNS**    | `https://cloudflare-dns.com/dns-query`             | `1.1.1.1`, `1.0.0.1`                 | `2606:4700:4700::1111`, `2606:4700:4700::1001` | Privacy-focused, fast performance        | [Cloudflare DNS](https://one.one.one.one)                           | DNS over HTTPS (DoH), DNS over TLS (DoT), strong privacy protection, supports ESNI               | Free                                                                             |
| **AdGuard DNS**       | `https://dns.adguard.com/dns-query`                | `94.140.14.14`, `94.140.15.15`       | `2a10:50c0::ad1:ff`, `2a10:50c0::ad2:ff`       | Ad-blocking, privacy protection          | [AdGuard DNS](https://adguard-dns.io)                               | Blocks ads, trackers, phishing sites, malware, and adult content, customizable filtering         | Available Free (basic), Paid (premium filtering options)                         |
| **Quad9 DNS**         | `https://dns.quad9.net/dns-query`                  | `9.9.9.9`, `149.112.112.112`         | `2620:fe::fe`, `2620:fe::9`                    | Security and malware protection          | [Quad9 DNS](https://www.quad9.net)                                  | Filters malicious domains, partners with security firms for threat intelligence, privacy-focused | Free                                                                             |
| **OpenDNS**           | `https://doh.opendns.com/dns-query`                | `208.67.222.222`, `208.67.220.220`   | `2620:0:ccc::2`, `2620:0:ccd::2`               | Parental control and security            | [OpenDNS](https://www.opendns.com)                                  | Offers family shield for content filtering, customizable filters, anti-phishing                  | Available Free (basic), Paid (premium with custom filtering)                     |
| **CleanBrowsing DNS** | `https://doh.cleanbrowsing.org/doh/family-filter/` | `185.228.168.168`, `185.228.169.168` | `2a0d:2a00:1::`, `2a0d:2a00:2::`               | Family-safe, content filtering           | [CleanBrowsing DNS](https://cleanbrowsing.org)                      | Family and adult filters, malware blocking, customizable plans for different use cases           | Available Free (basic), Paid (advanced filters)                                  |
| **NextDNS**           | `https://dns.nextdns.io`                           | `45.90.28.0`, `45.90.30.0`           | `2a07:a8c0::`, `2a07:a8c1::`                   | Highly customizable privacy and security | [NextDNS](https://my.nextdns.io)                                    | Fully customizable, blocks ads, trackers, malicious domains, and provides analytics              | Available Free (limited queries), Paid (unlimited queries and advanced settings) |
| **ControlD**          | `https://freedns.controld.com/p0`                  | `76.76.2.0`, `76.76.10.0`            | `2606:1a40::`, `2606:1a40:1::`                 | Customizable filtering, blocking         | [ControlD](https://controld.com)                                    | Multiple filtering modes (e.g., malware, ads, trackers), offers custom DNS profiles              | Available Free (basic profiles), Paid (customizable profiles)                    |
| **Comodo Secure DNS** | `https://doh.comodo.com/dns-query`                 | `8.26.56.26`, `8.20.247.20`          | Not available                                  | Security-focused, basic filtering        | [Comodo Secure DNS](https://www.comodo.com/secure-dns/)             | Focuses on blocking malware and phishing, no custom filtering                                    | Free                                                                             |
| **Yandex DNS**        | `https://dns.yandex.com/dns-query`                 | `77.88.8.8`, `77.88.8.1`             | `2a02:6b8::feed:0ff`, `2a02:6b8:0:1::feed:0ff` | Security, content filtering              | [Yandex DNS](https://dns.yandex.com)                                | Offers basic, safe, and family filtering options, content protection, speed-optimized            | Free                                                                             |

For a more comprehensive list of DNS providers, visit [AdGuard DNS Providers](https://adguard-dns.io/kb/general/dns-providers/).

## DNS Provider comparison metrics

The table includes a comprehensive DNS provider comparison with performance metrics, features, and official links:

| Provider                                                               | Latency | Privacy | Filtering | Logging  | DNSSEC | Support        | Features                               | DoH Endpoint                            | IPv4 Primary    | IPv6 Primary              |
| ---------------------------------------------------------------------- | ------- | ------- | --------- | -------- | ------ | -------------- | -------------------------------------- | --------------------------------------- | --------------- | ------------------------- |
| [Cloudflare](https://1.1.1.1)                                          | ✓✓✓     | ✓✓✓     | Optional  | No       | Yes    | 24/7           | Malware blocking, Family filter        | `https://dns.cloudflare.com/dns-query`  | 1.1.1.1         | 2606:4700:4700::1111      |
| [Google](https://developers.google.com/speed/public-dns)               | ✓✓✓     | ✓✓      | No        | Limited  | Yes    | Business Hours | Global load balancing                  | `https://dns.google/dns-query`          | 8.8.8.8         | 2001:4860:4860::8888      |
| [Quad9](https://quad9.net)                                             | ✓✓      | ✓✓✓     | Yes       | No       | Yes    | 24/7           | Threat blocking, EDNS                  | `https://dns.quad9.net/dns-query`       | 9.9.9.9         | 2620:fe::fe               |
| [AdGuard](https://adguard-dns.io)                                      | ✓✓      | ✓✓      | Yes       | Optional | Yes    | Business Hours | Ad blocking, Custom filters            | `https://dns.adguard.com/dns-query`     | 94.140.14.14    | 2a10:50c0::ad1:ff         |
| [OpenDNS](https://www.opendns.com)                                     | ✓✓      | ✓✓      | Yes       | Yes      | Yes    | 24/7           | Parental controls, Phishing protection | `https://doh.opendns.com/dns-query`     | 208.67.222.222  | 2620:119:35::35           |
| [NextDNS](https://nextdns.io)                                          | ✓✓✓     | ✓✓✓     | Yes       | Optional | Yes    | 24/7           | Custom blocklists, Analytics           | `https://dns.nextdns.io`                | 45.90.28.0      | 2a07:a8c0::               |
| [ControlD](https://controld.com)                                       | ✓✓✓     | ✓✓✓     | Yes       | No       | Yes    | Business Hours | Custom profiles, Geographic filters    | `https://freedns.controld.com/p0`       | 76.76.2.0       | 2606:1a40::               |
| [Mullvad](https://mullvad.net/en/help/dns-over-https-and-dns-over-tls) | ✓✓      | ✓✓✓     | Optional  | No       | Yes    | 24/7           | Ad blocking, No logging                | `https://doh.mullvad.net/dns-query`     | 194.242.2.2     | 2a07:e340::2              |
| [BlahDNS](https://blahdns.com)                                         | ✓✓      | ✓✓✓     | Yes       | No       | Yes    | Community      | Ad blocking, Privacy focused           | `https://doh-fi.blahdns.com/dns-query`  | 45.91.92.121    | 2a0e:dc0:6:23::2          |
| [LibreDNS](https://libredns.gr)                                        | ✓✓      | ✓✓✓     | Optional  | No       | Yes    | Community      | No filtering, Privacy focused          | `https://doh.libredns.gr/dns-query`     | 116.202.176.26  | 2a01:4f8:c17:ec67::1      |
| [DuckDNS](https://www.duckdns.org)                                     | ✓✓      | ✓✓✓     | No        | No       | Yes    | Limited        | Privacy focused                        | `https://basic.duckdns.org/dns-query`   | 185.199.108.153 | 2606:4700:3037::6815:8b99 |
| [Foundation for Applied Privacy](https://applied-privacy.net)          | ✓✓      | ✓✓✓     | No        | No       | Yes    | Limited        | GDPR compliant                         | `https://doh.applied-privacy.net/query` | 93.177.65.183   | 2a03:4000:38:53c::2       |
| [CZ.NIC ODVR](https://www.nic.cz/odvr)                                 | ✓✓      | ✓✓      | Optional  | Limited  | Yes    | Business Hours | Czech Republic based                   | `https://odvr.nic.cz/dns-query`         | 193.17.47.1     | 2001:148f:ffff::1         |
| [DNS.SB](https://dns.sb)                                               | ✓✓      | ✓✓      | No        | No       | Yes    | Limited        | Simple, Privacy focused                | `https://doh.dns.sb/dns-query`          | 185.222.222.222 | 2a09::                    |
| [PowerDNS](https://powerdns.org)                                       | ✓✓      | ✓✓      | Optional  | Limited  | Yes    | Community      | Self-hosted option                     | `https://doh.powerdns.org`              | Variable        | Variable                  |

### Legend

- Latency: ✓ (>100ms), ✓✓ (50-100ms), ✓✓✓ (<50ms)
- Privacy: ✓ (Basic), ✓✓ (Enhanced), ✓✓✓ (Maximum)
- Support: Community (Forum/Email), Limited (Email only), Business Hours (9-5 Support), 24/7 (Full Support)

### Additional Provider Features

#### Security Features

- **Malware Blocking**: Cloudflare, Quad9, NextDNS, ControlD
- **Phishing Protection**: OpenDNS, AdGuard, NextDNS
- **Threat Intelligence**: Quad9, NextDNS, ControlD
- **DDoS Protection**: Cloudflare, Google, NextDNS

#### Privacy Features

- **No-Log Policy**: Cloudflare, Mullvad, BlahDNS, LibreDNS
- **GDPR Compliance**: All EU-based providers
- **Anonymous Statistics**: NextDNS (optional), AdGuard (optional)
- **Privacy Audited**: Cloudflare, Mullvad

#### Filtering Options

- **Ad Blocking**: AdGuard, NextDNS, BlahDNS, ControlD
- **Family Filtering**: OpenDNS, AdGuard, NextDNS, ControlD
- **Custom Blocklists**: NextDNS, AdGuard, ControlD
- **Geographic Filtering**: ControlD, NextDNS

#### Technical Features

- **EDNS Client Subnet**: Google, OpenDNS
- **DNSSec Validation**: All listed providers
- **DNS64 Support**: Cloudflare, Google, NextDNS
- **ECS Support**: Google, OpenDNS, PowerDNS

### Provider Selection Considerations

1. **Performance Priority**
   
   - Local users: Cloudflare, Google, NextDNS
   - Global users: Cloudflare, Google, ControlD

2. **Privacy Priority**
   
   - Maximum privacy: Mullvad, LibreDNS, BlahDNS
   - No logging: Cloudflare, Mullvad, LibreDNS

3. **Filtering Priority**
   
   - Ad blocking: AdGuard, NextDNS, BlahDNS
   - Family protection: OpenDNS, ControlD, NextDNS

4. **Enterprise Usage**
   
   - Corporate environments: Google, Cloudflare, OpenDNS
   - Custom deployment: PowerDNS, OpenDNS, NextDNS

## Conclusion

This guide provides a detailed method to set up DNS over HTTPS on your Linux machine using `cloudflared`, ensuring your DNS queries are encrypted and secure. Select a DNS provider from the examples above or from the [AdGuard DNS Providers](https://adguard-dns.io/kb/general/dns-providers/) list to complete your setup.
