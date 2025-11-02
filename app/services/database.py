import sqlite3
from flask import current_app

def init_db():
    """Initialize SQLite database."""
    db_path = current_app.config['DB_PATH']
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS ping_history (id INTEGER PRIMARY KEY, provider TEXT, time TEXT, ping REAL, doh_ok INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS dns_lookup_history (id INTEGER PRIMARY KEY, domain TEXT, time TEXT, result TEXT)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ping_provider_time ON ping_history(provider, time)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_dns_time ON dns_lookup_history(time)")
    conn.commit()
    conn.close()

def cleanup_old_records():
    """Purge records older than configured retention hours."""
    db_path = current_app.config['DB_PATH']
    hrs = current_app.config['RETENTION_HOURS']
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(f"DELETE FROM ping_history WHERE time <= datetime('now','-{hrs} hours')")
    c.execute(f"DELETE FROM dns_lookup_history WHERE time <= datetime('now','-{hrs} hours')")
    conn.commit()
    conn.close()
