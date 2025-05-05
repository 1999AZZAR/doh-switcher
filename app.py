import os
import config
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flasgger import Swagger
import json
import logging
import subprocess
import re
from functools import wraps
from urllib.parse import urlparse
import datetime
import time
from flask_socketio import SocketIO
import requests
import sqlite3

app = Flask(__name__)
# load configuration
app.config.from_object(config)
app.secret_key = app.config['SECRET_KEY']
Swagger(app)

socketio = SocketIO(app)

# Constants
PROVIDERS_FILE = "doh_providers.json"
BACKUP_FILE = "doh_providers_backup.json"
SERVICE_FILES = ["/etc/systemd/system/cloudflared.service"]
DEFAULT_PROVIDERS = [
    {"name": "Cloudflare", "url": "https://cloudflare-dns.com/dns-query"},
    {"name": "Google", "url": "https://dns.google/dns-query"},
    {"name": "Quad9", "url": "https://dns.quad9.net/dns-query"},
    {"name": "NextDNS", "url": "https://dns.nextdns.io/dns-query"},
    {"name": "OpenDNS", "url": "https://opendns.com/dns-query"},
    {"name": "AdGuard", "url": "https://dns.adguard.com/dns-query"},
    {"name": "SecureDNS", "url": "https://doh.securedns.eu/dns-query"},
]

# Configure logging
# log file path from config
DEFAULT_LOG_FILE = app.config['LOG_FILE']
# Ensure log directory exists
log_dir = os.path.dirname(DEFAULT_LOG_FILE)
if not os.path.exists(log_dir):
    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception as e:
        print(f"Error creating log directory {log_dir}: {e}")
logging.basicConfig(
    filename=DEFAULT_LOG_FILE,
    level=logging.DEBUG,  # Keep DEBUG for detailed logging during testing
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Cache for test results
test_results = {}
ping_history = {}  # in-memory history for WebSocket; persisted in DB

# database path from config
DB_PATH = app.config['DB_PATH']

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS ping_history (id INTEGER PRIMARY KEY, provider TEXT, time TEXT, ping REAL, doh_ok INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS dns_lookup_history (id INTEGER PRIMARY KEY, domain TEXT, time TEXT, result TEXT)")
    # create indexes for retention and query efficiency
    c.execute("CREATE INDEX IF NOT EXISTS idx_ping_provider_time ON ping_history(provider, time)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_dns_time ON dns_lookup_history(time)")
    conn.commit()
    conn.close()

# initialize SQLite DB
init_db()

def log_event(message, level="info"):
    """Log events with specified level."""
    logger = logging.getLogger()
    getattr(logger, level)(message)


def initialize_providers_file():
    """Create doh_providers.json with default providers if it doesn't exist."""
    if not os.path.exists(PROVIDERS_FILE):
        try:
            with open(PROVIDERS_FILE, "w") as file:
                json.dump(DEFAULT_PROVIDERS, file, indent=4)
            log_event(f"Created {PROVIDERS_FILE} with default providers.")
        except IOError as e:
            log_event(f"Error creating {PROVIDERS_FILE}: {e}", "error")
            flash(f"Error creating providers file: {e}", "danger")


def load_providers():
    """Load providers from file or initialize with defaults."""
    initialize_providers_file()
    try:
        with open(PROVIDERS_FILE, "r") as file:
            providers = json.load(file)
            # Ensure all providers have required fields
            for provider in providers:
                if not all(key in provider for key in ["name", "url"]):
                    raise ValueError("Invalid provider format")
            return providers
    except (json.JSONDecodeError, IOError, ValueError) as e:
        log_event(f"Error loading providers file: {e}", "error")
        flash(f"Error loading providers file: {e}", "danger")
        return DEFAULT_PROVIDERS


def save_providers(providers):
    """Save providers to file."""
    try:
        with open(PROVIDERS_FILE, "w") as file:
            json.dump(providers, file, indent=4)
        log_event("Providers saved successfully.")
    except IOError as e:
        log_event(f"Error saving providers file: {e}", "error")
        flash(f"Error saving providers: {e}", "danger")
        raise


def update_doh_service(doh_url):
    """Update the cloudflared service with the new DoH URL."""
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

        subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
        subprocess.run(["sudo", "systemctl", "restart", "cloudflared"], check=True)
        log_event(f"Updated DoH URL to: {doh_url}")
    except (IOError, subprocess.CalledProcessError) as e:
        log_event(f"Error updating service file: {e}", "error")
        flash(f"Error updating service: {e}", "danger")
        raise


def validate_doh_url(url):
    """Validate a DoH URL by pinging its hostname."""
    try:
        ping_result = ping_provider(url)
        if ping_result == "Failed" or ping_result == "N/A":
            log_event(
                f"DoH validation failed for {url}: Ping failed or no RTT", "error"
            )
            return False
        log_event(f"DoH validation succeeded for {url}: Ping RTT={ping_result}ms")
        return True
    except Exception as e:
        log_event(f"DoH validation error for {url}: {e}", "error")
        return False


def normalize_url(url):
    """Normalize URL by removing trailing slashes and ensuring scheme."""
    parsed = urlparse(url)
    if not parsed.scheme:
        url = f"https://{url}"
        parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"


def get_current_doh_provider():
    """Get the current DoH provider from the service file."""
    try:
        with open(SERVICE_FILES[0], "r") as file:
            content = file.read()
            match = re.search(r"--upstream\s+(https?://[^\s/]+(?:/[^\s]*)?)", content)
            if match:
                full_url = match.group(1)
                base_url = normalize_url(full_url)
                providers = load_providers()
                for provider in providers:
                    if normalize_url(provider["url"]) == base_url:
                        return provider["name"], full_url, base_url
                return f"Unknown ({full_url})", full_url, base_url
        return "Unknown", "Unknown", "Unknown"
    except IOError as e:
        log_event(f"Error reading service file: {e}", "error")
        flash(f"Error reading service file: {e}", "danger")
        return "Unknown", "Unknown", "Unknown"


def get_service_status():
    """Check if the cloudflared service is running."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", "cloudflared"], check=False
        )
        return "running" if result.returncode == 0 else "not running"
    except subprocess.CalledProcessError as e:
        log_event(f"Error checking service status: {e}", "error")
        return "not running"


def ping_provider(url):
    """Ping the provider's hostname and return the average RTT."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        result = subprocess.run(
            ["ping", "-c", "3", "-W", "2", hostname], capture_output=True, text=True
        )
        if result.returncode == 0:
            match = re.search(r"rtt min/avg/max/mdev = [\d.]+/([\d.]+)/", result.stdout)
            if match:
                return round(float(match.group(1)), 2)
            return "N/A"
        return "Failed"
    except Exception as e:
        log_event(f"Ping error for {url}: {e}", "error")
        return "Failed"


def require_sudo(f):
    """Decorator to ensure the app runs with sudo privileges."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if os.geteuid() != 0:
            flash("This application must be run with sudo privileges.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)

    return decorated_function


def get_network_info():
    info = {"local_ip": None, "gateway": None, "dns_servers": []}
    try:
        result = subprocess.run(["ip", "route", "get", "8.8.8.8"], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            m = re.search(r"src\s+(\S+)", result.stdout)
            if m:
                info["local_ip"] = m.group(1)
            m2 = re.search(r"via\s+(\S+)", result.stdout)
            if m2:
                info["gateway"] = m2.group(1)
    except Exception as e:
        log_event(f"Error getting network route info: {e}", "error")
    try:
        with open("/etc/resolv.conf") as f:
            for line in f:
                if line.startswith("nameserver"):
                    parts = line.split()
                    if len(parts) >= 2:
                        info["dns_servers"].append(parts[1])
    except Exception as e:
        log_event(f"Error reading resolv.conf: {e}", "error")
    return info


@app.route("/")
def index():
    providers = load_providers()
    current_provider_name, full_provider, base_provider = get_current_doh_provider()
    service_status = get_service_status()
    network_info = get_network_info()
    return render_template(
        "index.html",
        providers=providers,
        current_provider_name=current_provider_name,
        full_provider=full_provider,
        base_provider=base_provider,
        service_status=service_status,
        network_info=network_info,
        default_providers=DEFAULT_PROVIDERS,
        test_results=test_results,
        test_interval=app.config['TEST_INTERVAL']
    )


@app.route("/select_provider", methods=["POST"])
@require_sudo
def select_provider():
    url = request.form.get("url")
    name = request.form.get("name")
    if not url or not name:
        flash("Provider name and URL are required.", "danger")
        return redirect(url_for("index"))
    try:
        update_doh_service(url)
        flash(f"Updated DoH to: {name}", "success")
        log_event(f"Updated DoH to: {name} ({url})")
    except Exception as e:
        flash(f"Error updating provider: {e}", "danger")
        log_event(f"Error updating provider: {e}", "error")
    return redirect(url_for("index"))


@app.route("/add_provider", methods=["POST"])
@require_sudo
def add_provider():
    name = request.form.get("name").strip()
    url = request.form.get("url").strip()
    if not name or not url:
        flash("Provider name and URL cannot be empty.", "danger")
        return redirect(url_for("index"))

    normalized_url = normalize_url(url)
    if not validate_doh_url(normalized_url):
        flash(
            f"Invalid DoH URL: {url}. The server is not reachable. Please verify the URL and try again.",
            "danger",
        )
        log_event(f"Failed to add provider {name}: Invalid DoH URL {url}", "error")
        return redirect(url_for("index"))

    providers = load_providers()
    # Check if provider already exists
    if any(p["url"] == normalized_url for p in providers):
        flash(f"Provider with URL {url} already exists.", "warning")
        return redirect(url_for("index"))

    new_provider = {"name": name, "url": normalized_url}
    providers.append(new_provider)
    try:
        save_providers(providers)
        update_doh_service(normalized_url)
        flash(f"Added and updated to provider: {name}", "success")
        log_event(f"Added provider: {name} ({normalized_url})")
    except Exception as e:
        flash(f"Error adding provider: {e}", "danger")
        log_event(f"Error adding provider {name}: {e}", "error")
    return redirect(url_for("index"))


@app.route("/delete_provider", methods=["POST"])
@require_sudo
def delete_provider():
    name = request.form.get("name")
    url = request.form.get("url")
    providers = load_providers()
    normalized_url = normalize_url(url)
    provider = next(
        (p for p in providers if p["url"] == normalized_url and p["name"] == name), None
    )
    if provider and provider not in DEFAULT_PROVIDERS:
        providers.remove(provider)
        try:
            save_providers(providers)
            flash(f"Deleted provider: {name}", "success")
            log_event(f"Deleted provider: {name} ({url})")
        except Exception as e:
            flash(f"Error deleting provider: {e}", "danger")
            log_event(f"Error deleting provider: {e}", "error")
    else:
        flash("Provider not found or is default.", "danger")
    return redirect(url_for("index"))


@app.route("/backup", methods=["POST"])
@require_sudo
def backup():
    try:
        with open(PROVIDERS_FILE, "r") as src, open(BACKUP_FILE, "w") as dst:
            dst.write(src.read())
        flash("Configuration backed up successfully.", "success")
        log_event("Configuration backed up.")
    except IOError as e:
        flash(f"Error backing up configuration: {e}", "danger")
        log_event(f"Error backing up configuration: {e}", "error")
    return redirect(url_for("index"))


@app.route("/restore", methods=["POST"])
@require_sudo
def restore():
    if not os.path.exists(BACKUP_FILE):
        flash("No backup file found.", "warning")
        return redirect(url_for("index"))
    try:
        with open(BACKUP_FILE, "r") as src, open(PROVIDERS_FILE, "w") as dst:
            dst.write(src.read())
        flash("Configuration restored successfully.", "success")
        log_event("Configuration restored.")
    except IOError as e:
        flash(f"Error restoring configuration: {e}", "danger")
        log_event(f"Error restoring configuration: {e}", "error")
    return redirect(url_for("index"))


@app.route("/test_providers", methods=["POST"])
def test_providers():
    try:
        cleanup_old_records()
        global test_results
        providers = load_providers()
        test_results = {}
        for provider in providers:
            url = provider["url"]
            ping_result = ping_provider(url)
            test_results[url] = {"ping": ping_result}
            log_event(f"Tested {provider['name']}: Ping={ping_result}")
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            doh_ok = doh_query_test(url)
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            ping_val = ping_result if isinstance(ping_result, (int, float)) else None
            c.execute(
                "INSERT INTO ping_history(provider, time, ping, doh_ok) VALUES (?,?,?,?)",
                (url, ts, ping_val, int(doh_ok))
            )
            conn.commit()
            conn.close()
        flash("All provider tests completed.", "success")
    except Exception as e:
        log_event(f"Error testing providers: {e}", "error")
        flash(f"Error testing providers: {e}", "danger")
    return redirect(url_for("index"))


@app.route("/test_provider", methods=["POST"])
def test_provider():
    try:
        cleanup_old_records()
        global test_results
        url = request.form.get("url")
        name = request.form.get("name")
        if not url or not name:
            raise ValueError("Provider name and URL are required")
        ping_result = ping_provider(url)
        test_results[url] = {"ping": ping_result}
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        doh_ok = doh_query_test(url)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        ping_val = ping_result if isinstance(ping_result, (int, float)) else None
        c.execute(
            "INSERT INTO ping_history(provider, time, ping, doh_ok) VALUES (?,?,?,?)",
            (url, ts, ping_val, int(doh_ok))
        )
        conn.commit()
        conn.close()
        flash(f"Test completed for {name}.", "success")
        log_event(f"Tested {name}: Ping={ping_result}")
    except Exception as e:
        log_event(f"Error testing provider {name if locals().get('name') else url}: {e}", "error")
        flash(f"Error testing provider: {e}", "danger")
    return redirect(url_for("index"))


# Edit provider routes
@app.route("/edit_provider/<int:index>")
@require_sudo
def edit_provider(index):
    providers = load_providers()
    if index < 0 or index >= len(providers):
        flash("Invalid provider index", "danger")
        return redirect(url_for("index"))
    if providers[index] in DEFAULT_PROVIDERS:
        flash("Cannot edit default provider", "danger")
        return redirect(url_for("index"))
    provider = providers[index]
    return render_template("edit_provider.html", index=index, provider=provider)

@app.route("/update_provider/<int:index>", methods=["POST"])
@require_sudo
def update_provider(index):
    providers = load_providers()
    if index < 0 or index >= len(providers):
        flash("Invalid provider index", "danger")
        return redirect(url_for("index"))
    if providers[index] in DEFAULT_PROVIDERS:
        flash("Cannot edit default provider", "danger")
        return redirect(url_for("index"))
    name = request.form.get("name").strip()
    url = request.form.get("url").strip()
    if not name or not url:
        flash("Name and URL cannot be empty", "danger")
        return redirect(url_for("edit_provider", index=index))
    normalized_url = normalize_url(url)
    if not validate_doh_url(normalized_url):
        flash(f"Invalid DoH URL: {url}. The server is not reachable. Please verify the URL and try again.", "danger")
        return redirect(url_for("edit_provider", index=index))
    for idx, p in enumerate(providers):
        if idx != index and normalize_url(p["url"]) == normalized_url:
            flash(f"Provider with URL {url} already exists.", "warning")
            return redirect(url_for("edit_provider", index=index))
    providers[index]["name"] = name
    providers[index]["url"] = normalized_url
    try:
        save_providers(providers)
        update_doh_service(normalized_url)
        flash(f"Provider updated: {name}", "success")
        log_event(f"Updated provider: {name} ({normalized_url})")
    except Exception as e:
        flash(f"Error updating provider: {e}", "danger")
        log_event(f"Error updating provider: {e}", "error")
    return redirect(url_for("index"))


# Service control routes
@app.route("/start_service", methods=["POST"])
@require_sudo
def start_service():
    try:
        subprocess.run(["sudo", "systemctl", "start", "cloudflared"], check=True)
        flash("Service started.", "success")
        log_event("Service started.")
    except subprocess.CalledProcessError as e:
        log_event(f"Error starting service: {e}", "error")
        flash(f"Error starting service: {e}", "danger")
    return redirect(url_for("index"))

@app.route("/stop_service", methods=["POST"])
@require_sudo
def stop_service():
    try:
        subprocess.run(["sudo", "systemctl", "stop", "cloudflared"], check=True)
        flash("Service stopped.", "success")
        log_event("Service stopped.")
    except subprocess.CalledProcessError as e:
        log_event(f"Error stopping service: {e}", "error")
        flash(f"Error stopping service: {e}", "danger")
    return redirect(url_for("index"))

@app.route("/restart_service", methods=["POST"])
@require_sudo
def restart_service():
    try:
        subprocess.run(["sudo", "systemctl", "restart", "cloudflared"], check=True)
        flash("Service restarted.", "success")
        log_event("Service restarted.")
    except subprocess.CalledProcessError as e:
        log_event(f"Error restarting service: {e}", "error")
        flash(f"Error restarting service: {e}", "danger")
    return redirect(url_for("index"))


# API endpoint for real-time metrics
@app.route("/api/status")
@require_sudo
def api_status():
    _, full_url, base = get_current_doh_provider()
    service_status = get_service_status()
    network_info = get_network_info()
    current_ping = None
    try:
        current_ping = ping_provider(full_url)
    except Exception:
        current_ping = None
    history = ping_history.get(base, [])
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    history.append({"time": ts, "ping": current_ping})
    if len(history) > 20:
        history.pop(0)
    ping_history[base] = history
    return jsonify({
        "service_status": service_status,
        "network_info": network_info,
        "current_ping": current_ping,
        "ping_history": history,
    })

@app.route("/api/lookup", methods=["POST"])
@require_sudo
def api_lookup():
    # clean old DNS lookup records before inserting
    cleanup_old_records()
    data = request.get_json() or request.form
    domain = data.get("domain")
    if not domain:
        return jsonify({"error": "No domain provided"}), 400
    domain = domain.strip()
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        res = subprocess.run(["dig", "+short", domain], capture_output=True, text=True, check=True)
        result = res.stdout.splitlines()
    except subprocess.CalledProcessError:
        result = []
    # record lookup in SQLite
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO dns_lookup_history(domain, time, result) VALUES (?,?,?)",
        (domain, ts, json.dumps(result))
    )
    conn.commit()
    # fetch recent lookup history
    c.execute(
        "SELECT time, domain, result FROM dns_lookup_history ORDER BY time DESC LIMIT 20"
    )
    rows = c.fetchall()
    conn.close()
    history = [{"time": r[0], "domain": r[1], "result": json.loads(r[2])} for r in rows]
    return jsonify({"time": ts, "domain": domain, "result": result, "history": history})

@app.route("/api/ping_history", methods=["GET"])
@require_sudo
def api_ping_history():
    provider = request.args.get("provider")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT time, ping FROM ping_history WHERE provider = ? ORDER BY time DESC LIMIT 20",
        (provider,)
    )
    rows = c.fetchall()
    conn.close()
    history = [{"time": r[0], "ping": r[1]} for r in rows]
    return jsonify({provider: history})

@app.route("/api/clear_ping_history", methods=["POST"])
@require_sudo
def clear_ping_history():
    data = request.get_json() or request.form
    provider = data.get("provider")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if provider:
        c.execute("DELETE FROM ping_history WHERE provider = ?", (provider,))
    else:
        c.execute("DELETE FROM ping_history")
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


# Analytics endpoint for ping history stats
@app.route("/api/analytics", methods=["GET"])
@require_sudo
def api_analytics():
    """Compute ping stats from in-memory JSON history."""
    provider = request.args.get("provider")
    recs = ping_history.get(provider, [])
    # filter only numeric pings
    vals = [r.get("ping") for r in recs if isinstance(r.get("ping"), (int, float))]
    if vals:
        mn = min(vals)
        mx = max(vals)
        avg = round(sum(vals) / len(vals), 2)
        count = len(vals)
    else:
        mn = mx = avg = None
        count = 0
    return jsonify({
        "provider": provider,
        "min": mn,
        "max": mx,
        "avg": avg,
        "count": count
    })

# DNS-over-HTTPS validation
def doh_query_test(url):
    """Perform a DNS-over-HTTPS query to validate service."""
    try:
        r = requests.get(f"{url}?name=example.com&type=A", headers={"Accept":"application/dns-json"}, timeout=3)
        data = r.json()
        return "Answer" in data and bool(data.get("Answer"))
    except Exception as e:
        log_event(f"DoH query error for {url}: {e}", "error")
        return False

# Automatic retention: purge records older than 6 hours
def cleanup_old_records():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    hrs = app.config['RETENTION_HOURS']
    c.execute(f"DELETE FROM ping_history WHERE time <= datetime('now','-{hrs} hours')")
    c.execute(f"DELETE FROM dns_lookup_history WHERE time <= datetime('now','-{hrs} hours')")
    conn.commit()
    conn.close()

# Background thread for real-time status events
def background_thread():
    """Send status_update events every 5 seconds, and clean old records."""
    while True:
        cleanup_old_records()
        _, full_url, base = get_current_doh_provider()
        status = get_service_status()
        net = get_network_info()
        ping = None
        try:
            ping = ping_provider(full_url)
        except:
            ping = None
        doh_ok = doh_query_test(full_url)
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # update history
        hist = ping_history.get(base, [])
        ping_val = ping if isinstance(ping, (int, float)) else None
        hist.append({"time": ts, "ping": ping_val, "doh_ok": doh_ok})
        if len(hist) > 100:
            hist.pop(0)
        ping_history[base] = hist
        # insert into SQLite DB
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        ping_val = ping if isinstance(ping, (int, float)) else None
        c.execute(
            "INSERT INTO ping_history(provider, time, ping, doh_ok) VALUES (?,?,?,?)",
            (base, ts, ping_val, int(doh_ok))
        )
        conn.commit()
        conn.close()
        socketio.emit("status_update", {
            "time": ts,
            "service_status": status,
            "network_info": net,
            "current_ping": ping,
            "doh_ok": doh_ok,
            "ping_history": hist
        }, broadcast=True)
        socketio.sleep(app.config['TEST_INTERVAL'])

if __name__ == "__main__":
    # start background task for real-time updates
    socketio.start_background_task(background_thread)
    socketio.run(app, debug=False, host="0.0.0.0", port=5003)
