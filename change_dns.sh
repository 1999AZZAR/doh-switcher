#!/usr/bin/env bash
exec >/dev/null 2>&1

# Directory where the web UI is installed
APP_DIR="/opt/doh-switcher"
VENV="$APP_DIR/venv"
PYTHON="$VENV/bin/python"

# Launch the Flask web UI quietly (suppress logs)
nohup sudo "$PYTHON" "$APP_DIR/app.py" >/dev/null 2>&1 &
sleep 2

# Open the default web browser to the application's URL (no output)
xdg-open "http://127.0.0.1:5003" >/dev/null 2>&1 &

exit 0
