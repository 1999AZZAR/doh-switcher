import os
import json
import sys
import requests
import logging
from colorama import Fore, Style, init

# Initialize colorama for colored output
init()

# Constants
PROVIDERS_FILE = "doh_providers.json"
BACKUP_FILE = "doh_providers_backup.json"
DEFAULT_PROVIDERS = [
    {"name": "Cloudflare", "url": "https://cloudflare-dns.com/dns-query"},
    {"name": "Google", "url": "https://dns.google/dns-query"},
    {"name": "Quad9", "url": "https://dns.quad9.net/dns-query"},
    {"name": "NextDNS", "url": "https://dns.nextdns.io"},
    {"name": "AdGuard", "url": "https://dns.adguard.com/dns-query"},
]

# Configure logging
logging.basicConfig(
    filename="doh_manager.log", level=logging.INFO, format="%(asctime)s - %(message)s"
)


# Log events
def log_event(message):
    logging.info(message)


# Load DoH providers from file or use default providers
def load_providers():
    if os.path.exists(PROVIDERS_FILE):
        try:
            with open(PROVIDERS_FILE, "r") as file:
                return json.load(file)
        except (json.JSONDecodeError, IOError) as e:
            print(
                Fore.RED
                + f"Error loading providers file: {e}. Using default providers."
                + Style.RESET_ALL
            )
    return DEFAULT_PROVIDERS


# Save DoH providers to file
def save_providers(providers):
    try:
        with open(PROVIDERS_FILE, "w") as file:
            json.dump(providers, file, indent=4)
    except IOError as e:
        print(Fore.RED + f"Error saving providers file: {e}" + Style.RESET_ALL)


# Set file permissions for service files
def set_permissions(mode):
    for file in SERVICE_FILES:
        try:
            os.chmod(file, mode)
        except OSError as e:
            print(
                Fore.RED
                + f"Error setting permissions for {file}: {e}"
                + Style.RESET_ALL
            )


# Get current permissions of the first service file
def get_current_permissions():
    try:
        return oct(os.stat(SERVICE_FILES[0]).st_mode)[-3:]
    except OSError as e:
        print(Fore.RED + f"Error getting file permissions: {e}" + Style.RESET_ALL)
        return "000"


# Update the cloudflared service with a new DoH URL
def update_doh_service(doh_url):
    service_file = SERVICE_FILES[0]
    try:
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

        # Reload and restart the service
        os.system("sudo systemctl daemon-reload")
        os.system("sudo systemctl restart cloudflared")
        print(Fore.GREEN + f"Updated DoH URL to: {doh_url}" + Style.RESET_ALL)
        log_event(f"Updated DoH URL to: {doh_url}")
    except IOError as e:
        print(Fore.RED + f"Error updating service file: {e}" + Style.RESET_ALL)


# Clear the terminal screen
def clear_terminal():
    os.system("cls" if os.name == "nt" else "clear")


# Validate DoH URL
def validate_doh_url(url):
    try:
        response = requests.get(url, params={"dns": "example.com"}, timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False


# Get the current DoH provider
def get_current_doh_provider():
    try:
        with open(SERVICE_FILES[0], "r") as file:
            for line in file:
                if line.strip().startswith("ExecStart="):
                    parts = line.strip().split()
                    for part in parts:
                        if part.startswith("--upstream"):
                            upstream = part.split("=")
                            if len(upstream) > 1:
                                return upstream[1]
    except IOError as e:
        print(Fore.RED + f"Error reading service file: {e}" + Style.RESET_ALL)
    return "Unknown"


# Delete a custom provider
def delete_custom_provider(providers):
    custom_providers = [p for p in providers if p not in DEFAULT_PROVIDERS]
    if not custom_providers:
        print(Fore.YELLOW + "No custom providers to delete." + Style.RESET_ALL)
        return providers

    print("\nCustom Providers:")
    for idx, provider in enumerate(custom_providers):
        print(f"{idx + 1}. {provider['name']} ({provider['url']})")

    choice = (
        input("Enter the number of the provider to delete (or 'q' to cancel): ")
        .strip()
        .lower()
    )
    if choice == "q":
        print(Fore.YELLOW + "Deletion canceled." + Style.RESET_ALL)
        return providers

    if choice.isdigit():
        index = int(choice) - 1
        if 0 <= index < len(custom_providers):
            providers.remove(custom_providers[index])
            save_providers(providers)
            print(
                Fore.GREEN
                + f"Deleted provider: {custom_providers[index]['name']}"
                + Style.RESET_ALL
            )
            log_event(f"Deleted provider: {custom_providers[index]['name']}")
        else:
            print(Fore.RED + "Invalid selection." + Style.RESET_ALL)
    return providers


# Backup configuration
def backup_config():
    try:
        with open(PROVIDERS_FILE, "r") as src, open(BACKUP_FILE, "w") as dst:
            dst.write(src.read())
        print(
            Fore.GREEN + f"Configuration backed up to {BACKUP_FILE}" + Style.RESET_ALL
        )
        log_event("Configuration backed up.")
    except IOError as e:
        print(Fore.RED + f"Error backing up configuration: {e}" + Style.RESET_ALL)


# Restore configuration
def restore_config():
    if not os.path.exists(BACKUP_FILE):
        print(Fore.YELLOW + "No backup file found." + Style.RESET_ALL)
        return

    try:
        with open(BACKUP_FILE, "r") as src, open(PROVIDERS_FILE, "w") as dst:
            dst.write(src.read())
        print(
            Fore.GREEN + f"Configuration restored from {BACKUP_FILE}" + Style.RESET_ALL
        )
        log_event("Configuration restored.")
    except IOError as e:
        print(Fore.RED + f"Error restoring configuration: {e}" + Style.RESET_ALL)


# Check service status
def check_service_status():
    status = os.system("systemctl is-active --quiet cloudflared")
    if status == 0:
        print(Fore.GREEN + "Service is running." + Style.RESET_ALL)
    else:
        print(Fore.RED + "Service is not running." + Style.RESET_ALL)


# Show help menu
def show_help():
    print(Fore.CYAN + "\n=== Help ===" + Style.RESET_ALL)
    print("1. Select a DoH provider by entering its number.")
    print("2. Press 't' to toggle file permissions.")
    print("3. Press 'c' to add a custom DoH provider.")
    print("4. Press 'd' to delete a custom provider.")
    print("5. Press 'b' to backup configuration.")
    print("6. Press 'r' to restore configuration.")
    print("7. Press 's' to check service status.")
    print("8. Press 'h' for help.")
    print("9. Press 'q' to quit.")


# Main TUI menu
def tui_menu():
    doh_providers = load_providers()

    while True:
        clear_terminal()  # Clear the terminal before displaying the menu
        print(Fore.CYAN + "\n=== DoH Provider Selection ===" + Style.RESET_ALL)
        print(f"Current DoH Provider: {get_current_doh_provider()}")
        print(f"File Permissions: {get_current_permissions()}")
        print("Press 't' to toggle file permissions.")
        print("Press 'c' to enter a custom DoH URL.")
        print("Press 'd' to delete a custom provider.")
        print("Press 'b' to backup configuration.")
        print("Press 'r' to restore configuration.")
        print("Press 's' to check service status.")
        print("Press 'h' for help.")
        print("Press 'q' to quit.\n")

        # List available providers
        for idx, provider in enumerate(doh_providers):
            print(f"{idx + 1}. {provider['name']}")

        choice = input("\nEnter your choice: ").strip().lower()

        if choice == "t":
            # Toggle file permissions
            current_mode = get_current_permissions()
            new_mode = 0o666 if current_mode == "600" else 0o600
            set_permissions(new_mode)
            print(
                Fore.GREEN
                + f"Toggled file permissions to: {oct(new_mode)[-3:]}"
                + Style.RESET_ALL
            )
            log_event(f"Toggled file permissions to: {oct(new_mode)[-3:]}")

        elif choice == "c":
            # Add a custom DoH provider
            custom_name = input(
                "Enter custom provider name (or 'q' to cancel): "
            ).strip()
            if custom_name == "q":
                print(
                    Fore.YELLOW + "Custom provider addition canceled." + Style.RESET_ALL
                )
                continue

            custom_url = input("Enter custom DoH URL (or 'q' to cancel): ").strip()
            if custom_url == "q":
                print(
                    Fore.YELLOW + "Custom provider addition canceled." + Style.RESET_ALL
                )
                continue

            if custom_name and custom_url:
                if validate_doh_url(custom_url):
                    doh_providers.append({"name": custom_name, "url": custom_url})
                    save_providers(doh_providers)
                    update_doh_service(custom_url)
                    print(
                        Fore.GREEN
                        + f"Added and updated to custom DoH URL: {custom_url}"
                        + Style.RESET_ALL
                    )
                    log_event(f"Added custom provider: {custom_name} ({custom_url})")
                else:
                    print(
                        Fore.RED
                        + "Invalid DoH URL. Please check the URL and try again."
                        + Style.RESET_ALL
                    )
            else:
                print(
                    Fore.RED
                    + "Invalid input. Name and URL cannot be empty."
                    + Style.RESET_ALL
                )

        elif choice == "d":
            # Delete a custom provider
            doh_providers = delete_custom_provider(doh_providers)

        elif choice == "b":
            # Backup configuration
            backup_config()

        elif choice == "r":
            # Restore configuration
            restore_config()

        elif choice == "s":
            # Check service status
            check_service_status()

        elif choice == "h":
            # Show help menu
            show_help()

        elif choice == "q":
            # Exit the program
            print(Fore.YELLOW + "Exiting..." + Style.RESET_ALL)
            clear_terminal()
            sys.exit(0)

        elif choice.isdigit():
            # Select a provider from the list
            index = int(choice) - 1
            if 0 <= index < len(doh_providers):
                selected_provider = doh_providers[index]
                update_doh_service(selected_provider["url"])
                print(
                    Fore.GREEN
                    + f"Updated DoH to: {selected_provider['name']}"
                    + Style.RESET_ALL
                )
                log_event(f"Updated DoH to: {selected_provider['name']}")
            else:
                print(
                    Fore.RED + "Invalid selection. Please try again." + Style.RESET_ALL
                )

        else:
            print(Fore.RED + "Invalid input. Please try again." + Style.RESET_ALL)

        input("\nPress Enter to continue...")  # Pause before clearing the screen


if __name__ == "__main__":
    SERVICE_FILES = ["/etc/systemd/system/cloudflared.service"]
    tui_menu()
