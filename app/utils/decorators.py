import os
from functools import wraps
from flask import flash, redirect, url_for

def require_sudo(f):
    """Decorator to ensure the app runs with sudo privileges."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if os.geteuid() != 0:
            flash("This application must be run with sudo privileges.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function
