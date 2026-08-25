# DoH Switcher Architecture

## Project Structure

The project follows Flask best practices with a modular architecture:

```
doh-switcher/
├── app/                          # Main application package
│   ├── __init__.py              # Flask app factory
│   ├── models.py                # Data models and constants
│   ├── routes.py                # Route handlers
│   ├── services/                # Business logic layer
│   │   ├── __init__.py
│   │   ├── database.py          # Database operations
│   │   ├── doh_service.py       # DoH service management
│   │   ├── monitoring.py        # Background monitoring tasks
│   │   ├── network_service.py   # Network utilities
│   │   ├── provider_service.py  # Provider CRUD operations
│   │   └── vpn_service.py       # VPN Privacy Mode management
│   └── utils/                   # Utility functions
│       ├── __init__.py
│       ├── decorators.py        # Custom decorators (require_sudo)
│       ├── logging.py           # Logging utilities
│       └── validators.py        # URL validation logic
├── static/                      # Static assets (CSS, JS)
│   └── css/
│       └── styles.css
├── templates/                   # Jinja2 templates
│   ├── index.html
│   ├── vpn.html                 # VPN settings screen
│   └── edit_provider.html
├── scripts/                     # Legacy and utility scripts
│   ├── app.py.bak              # Backup of monolithic app
│   ├── install_vpn_stack.sh    # Installs VPN privacy stack
│   └── change_dns.sh           # Core DNS change script
├── Prerequisites/               # Installation prerequisites
├── config.py                    # Configuration management
├── run.py                       # Application entry point
├── setup.py                     # Package setup for installation
├── requirements.txt             # Python dependencies
├── install.sh                   # Installation script
├── uninstall.sh                # Uninstallation script
└── README.md                    # Main documentation
```

## Architecture Layers

### 1. Presentation Layer (`templates/`, `static/`)

- Web UI using Jinja2 templates
- Tailwind CSS for styling
- WebSocket for real-time updates

### 2. Route Layer (`app/routes.py`)

- HTTP request handlers
- Form processing
- API endpoints
- Delegates to service layer

### 3. Service Layer (`app/services/`)

- **doh_service.py**: Manages cloudflared service operations
- **vpn_service.py**: Handles toggling between Cloudflared and the Unbound/DNSCrypt/WARP stack
- **provider_service.py**: Provider CRUD and configuration
- **network_service.py**: Network diagnostics and ping operations
- **database.py**: SQLite database operations
- **monitoring.py**: Background tasks for real-time monitoring

### 4. Utility Layer (`app/utils/`)

- **validators.py**: URL validation and normalization
- **decorators.py**: Custom decorators (sudo checks)
- **logging.py**: Centralized logging

### 5. Data Layer

- **SQLite Database**: Stores ping history and DNS lookup records
- **JSON Files**: Provider configuration storage
- **models.py**: Constants and in-memory state

## Key Design Patterns

### Application Factory Pattern

`app/__init__.py` uses the factory pattern:

```python
def create_app():
    app = Flask(__name__)
    # Configure and initialize
    return app
```

### Service Layer Pattern

Business logic is separated from routes:

```python
# routes.py - presentation
@app.route("/select_provider", methods=["POST"])
def select_provider():
    # Delegates to service
    update_doh_service(url)

# doh_service.py - business logic
def update_doh_service(doh_url):
    # Actual implementation
```

### Decorator Pattern

Reusable functionality via decorators:

```python
@app.route("/api/status")
@require_sudo
def api_status():
    # Protected route
```

## Data Flow

1. **User Request** → Route Handler (`routes.py`)
2. **Route Handler** → Service Layer (`services/`)
3. **Service Layer** → External Systems (systemd, network, DB)
4. **Response** ← Service Layer ← Route Handler

## Configuration Management

Uses environment variables with fallbacks:

```python
# config.py
SECRET_KEY = os.getenv("SECRET_KEY", "default_key")
LOG_FILE = os.getenv("LOG_FILE", "/var/log/doh-switcher.log")
```

## Database Schema

**ping_history**

- `id`: INTEGER PRIMARY KEY
- `provider`: TEXT (DoH URL)
- `time`: TEXT (timestamp)
- `ping`: REAL (latency in ms)
- `doh_ok`: INTEGER (1=success, 0=failure)

**dns_lookup_history**

- `id`: INTEGER PRIMARY KEY
- `domain`: TEXT
- `time`: TEXT (timestamp)
- `result`: TEXT (JSON array)

## Running the Application

### Development

```bash
sudo python run.py
```

### Production (systemd)

```bash
sudo systemctl start doh-switcher
sudo systemctl enable doh-switcher
```

## Testing Structure (To Be Implemented)

Recommended test structure:

```
tests/
├── __init__.py
├── test_services/
│   ├── test_doh_service.py
│   ├── test_provider_service.py
│   └── test_network_service.py
├── test_utils/
│   └── test_validators.py
└── test_routes.py
```

## Migration from Legacy

The monolithic `app.py` (722 lines) has been refactored into:

- `app/__init__.py` (48 lines) - App factory
- `app/routes.py` (389 lines) - Routes only
- `app/services/*.py` (~200 lines) - Business logic
- `app/utils/*.py` (~50 lines) - Utilities

This provides:

- Better separation of concerns
- Easier testing
- Improved maintainability
- Clearer code organization
