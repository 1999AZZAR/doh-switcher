DEFAULT_PROVIDERS = [
    {"name": "Cloudflare", "url": "https://cloudflare-dns.com/dns-query"},
    {"name": "Google", "url": "https://dns.google/dns-query"},
    {"name": "Quad9", "url": "https://dns.quad9.net/dns-query"},
    {"name": "NextDNS", "url": "https://dns.nextdns.io/dns-query"},
    {"name": "OpenDNS", "url": "https://opendns.com/dns-query"},
    {"name": "AdGuard", "url": "https://dns.adguard.com/dns-query"},
    {"name": "SecureDNS", "url": "https://doh.securedns.eu/dns-query"},
]

PROVIDERS_FILE = "doh_providers.json"
BACKUP_FILE = "doh_providers_backup.json"
SERVICE_FILES = ["/etc/systemd/system/cloudflared.service"]

# Cache for test results
test_results = {}
ping_history = {}
