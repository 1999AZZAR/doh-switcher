import datetime
import json
import sqlite3
import subprocess
from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from app.models import test_results, ping_history, DEFAULT_PROVIDERS
from app.services.provider_service import load_providers, save_providers, backup_config, restore_config
from app.services.dns_service import (
    update_dns_service, get_current_provider, get_service_status, 
    control_service, test_provider_resolution
)
from app.services.network_service import get_network_info, ping_provider
from app.services.database import cleanup_old_records
from app.utils.validators import normalize_url, validate_provider
from app.utils.decorators import require_sudo
from app.utils.logging import log_event
from app.services.vpn_service import is_vpn_mode_active, enable_vpn_mode, disable_vpn_mode


def register_routes(app):
    
    @app.route("/")
    def index():
        providers = load_providers()
        current_provider_name, full_provider, base_provider = get_current_provider()
        service_status = get_service_status()
        network_info = get_network_info()
        vpn_mode_active = is_vpn_mode_active()
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
            test_interval=app.config['TEST_INTERVAL'], vpn_mode_active=vpn_mode_active
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
            update_dns_service(url)
            flash(f"Updated DNS to: {name}", "success")
            log_event(f"Updated DNS to: {name} ({url})")
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
        if not validate_provider(normalized_url):
            flash(
                f"Invalid Provider URL/IP: {url}. The server is not reachable. Please verify the URL/IP and try again.",
                "danger",
            )
            log_event(f"Failed to add provider {name}: Invalid URL/IP {url}", "error")
            return redirect(url_for("index"))

        providers = load_providers()
        if any(p["url"] == normalized_url for p in providers):
            flash(f"Provider with URL {url} already exists.", "warning")
            return redirect(url_for("index"))

        new_provider = {"name": name, "url": normalized_url}
        providers.append(new_provider)
        try:
            save_providers(providers)
            update_dns_service(normalized_url)
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
        if backup_config():
            flash("Configuration backed up successfully.", "success")
        else:
            flash("Error backing up configuration.", "danger")
        return redirect(url_for("index"))

    @app.route("/restore", methods=["POST"])
    @require_sudo
    def restore():
        if restore_config():
            flash("Configuration restored successfully.", "success")
        else:
            flash("No backup file found.", "warning")
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
                ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                doh_ok = test_provider_resolution(url)
                conn = sqlite3.connect(app.config['DB_PATH'])
                c = conn.cursor()
                ping_val = ping_result if isinstance(ping_result, (int, float)) else None
                c.execute(
                    "INSERT INTO ping_history(provider, time, ping, doh_ok) VALUES (?,?,?,?)",
                    (url, ts, ping_val, int(doh_ok))
                )
                conn.commit()
                conn.close()
                log_event(f"Tested {provider['name']}: Ping={ping_result}")
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
            doh_ok = test_provider_resolution(url)
            conn = sqlite3.connect(app.config['DB_PATH'])
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
        if not validate_provider(normalized_url):
            flash(f"Invalid Provider URL/IP: {url}. The server is not reachable. Please verify and try again.", "danger")
            return redirect(url_for("edit_provider", index=index))
        for idx, p in enumerate(providers):
            if idx != index and normalize_url(p["url"]) == normalized_url:
                flash(f"Provider with URL {url} already exists.", "warning")
                return redirect(url_for("edit_provider", index=index))
        providers[index]["name"] = name
        providers[index]["url"] = normalized_url
        try:
            save_providers(providers)
            update_dns_service(normalized_url)
            flash(f"Provider updated: {name}", "success")
            log_event(f"Updated provider: {name} ({normalized_url})")
        except Exception as e:
            flash(f"Error updating provider: {e}", "danger")
            log_event(f"Error updating provider: {e}", "error")
        return redirect(url_for("index"))

    @app.route("/start_service", methods=["POST"])
    @require_sudo
    def start_service():
        if control_service("start"):
            flash("Service started.", "success")
        else:
            flash("Error starting service.", "danger")
        return redirect(url_for("index"))

    @app.route("/stop_service", methods=["POST"])
    @require_sudo
    def stop_service():
        if control_service("stop"):
            flash("Service stopped.", "success")
        else:
            flash("Error stopping service.", "danger")
        return redirect(url_for("index"))

    @app.route("/restart_service", methods=["POST"])
    @require_sudo
    def restart_service():
        if control_service("restart"):
            flash("Service restarted.", "success")
        else:
            flash("Error restarting service.", "danger")
        return redirect(url_for("index"))

    @app.route("/api/status")
    @require_sudo
    def api_status():
        _, full_url, base = get_current_provider()
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
        conn = sqlite3.connect(app.config['DB_PATH'])
        c = conn.cursor()
        c.execute(
            "INSERT INTO dns_lookup_history(domain, time, result) VALUES (?,?,?)",
            (domain, ts, json.dumps(result))
        )
        conn.commit()
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
        conn = sqlite3.connect(app.config['DB_PATH'])
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
        conn = sqlite3.connect(app.config['DB_PATH'])
        c = conn.cursor()
        if provider:
            c.execute("DELETE FROM ping_history WHERE provider = ?", (provider,))
        else:
            c.execute("DELETE FROM ping_history")
        conn.commit()
        conn.close()
        return jsonify({"status": "ok"})

    @app.route("/api/analytics", methods=["GET"])
    @require_sudo
    def api_analytics():
        provider = request.args.get("provider")
        recs = ping_history.get(provider, [])
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

    @app.route("/vpn_settings")
    @require_sudo
    def vpn_settings():
        return render_template("vpn.html", vpn_mode_active=is_vpn_mode_active())

    @app.route("/toggle_mode", methods=["POST"])
    @require_sudo
    def toggle_mode():
        if is_vpn_mode_active():
            if disable_vpn_mode():
                flash("VPN Mode disabled. Restored Cloudflared.", "success")
            else:
                flash("Error disabling VPN Mode.", "danger")
        else:
            if enable_vpn_mode():
                flash("VPN Mode enabled (Unbound + DNSCrypt + WARP).", "success")
            else:
                flash("Error enabling VPN Mode.", "danger")
        return redirect(request.referrer or url_for("index"))
