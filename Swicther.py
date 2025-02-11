import os
import json

PROVIDERS_FILE = "doh_providers.json"
FILES = [
    "/etc/systemd/system/cloudflared.service",
    "/etc/systemd/system/cloudflared.service.backup",
]


def load_providers():
    if os.path.exists(PROVIDERS_FILE):
        with open(PROVIDERS_FILE, "r") as file:
            return json.load(file)
    return [
        {"name": "Cloudflare", "url": "https://cloudflare-dns.com/dns-query"},
        {"name": "Google", "url": "https://dns.google/dns-query"},
        {"name": "Quad9", "url": "https://dns.quad9.net/dns-query"},
        {"name": "NextDNS", "url": "https://dns.nextdns.io"},
        {"name": "AdGuard", "url": "https://dns.adguard.com/dns-query"},
    ]


def save_providers(providers):
    with open(PROVIDERS_FILE, "w") as file:
        json.dump(providers, file, indent=4)


doh_providers = load_providers()


def set_permissions(mode):
    for file in FILES:
        os.chmod(file, mode)


def get_current_permissions():
    return oct(os.stat(FILES[0]).st_mode)[-3:]


def update_doh_service(doh_url):
    service_file = "/etc/systemd/system/cloudflared.service"
    with open(service_file, "r") as file:
        lines = file.readlines()
    with open(service_file, "w") as file:
        for line in lines:
            if line.strip().startswith("ExecStart="):
                file.write(
                    f"ExecStart=/usr/bin/cloudflared proxy-dns --port 53 --upstream {doh_url}\n"
                )
            else:
                file.write(line)
    os.system("sudo systemctl daemon-reload")
    os.system("sudo systemctl restart cloudflared")


def tui_menu():
    while True:
        print("\nSelect a DoH Provider:")
        print(f"File Permissions: {get_current_permissions()}")
        print("Press 't' to toggle file permissions.")

        for idx, provider in enumerate(doh_providers):
            print(f"{idx + 1}. {provider['name']}")

        print("Press 'c' to enter a custom DoH URL.")
        print("Press 'q' to exit.")

        key = input("Enter your choice: ").strip()

        if key == "t":
            current_mode = get_current_permissions()
            new_mode = 0o666 if current_mode == "600" else 0o600
            set_permissions(new_mode)
        elif key == "c":
            custom_name = input("Enter custom provider name: ").strip()
            custom_url = input("Enter custom DoH URL: ").strip()

            doh_providers.append({"name": custom_name, "url": custom_url})
            save_providers(doh_providers)
            update_doh_service(custom_url)
            print(f"Updated DoH to custom URL: {custom_url} and saved for future use.")
        elif key == "q":
            break
        elif key.isdigit() and 1 <= int(key) <= len(doh_providers):
            selected_provider = doh_providers[int(key) - 1]
            update_doh_service(selected_provider["url"])
            print(f"Updated DoH to: {selected_provider['name']}")


if __name__ == "__main__":
    tui_menu()
