import datetime
import sqlite3
from flask import current_app
from app import socketio
from app.models import ping_history
from app.services.doh_service import get_current_doh_provider, get_service_status, doh_query_test
from app.services.network_service import get_network_info, ping_provider
from app.services.database import cleanup_old_records

def background_thread():
    """Send status_update events periodically and clean old records."""
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
        
        # Update history
        hist = ping_history.get(base, [])
        ping_val = ping if isinstance(ping, (int, float)) else None
        hist.append({"time": ts, "ping": ping_val, "doh_ok": doh_ok})
        if len(hist) > 100:
            hist.pop(0)
        ping_history[base] = hist
        
        # Insert into SQLite DB
        db_path = current_app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
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
        socketio.sleep(current_app.config['TEST_INTERVAL'])
