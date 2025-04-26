from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

# Application configuration
SECRET_KEY = os.getenv("SECRET_KEY", "doh_switcher_secret_key")
LOG_FILE = os.getenv("LOG_FILE", "/var/log/doh-switcher.log")
DB_PATH = os.getenv("DB_PATH", "doh_history.db")
SERVICE_FILE = os.getenv("SERVICE_FILE", "/etc/systemd/system/cloudflared.service")
RETENTION_HOURS = int(os.getenv("RETENTION_HOURS", "6"))
TEST_INTERVAL = int(os.getenv("TEST_INTERVAL", "5"))
