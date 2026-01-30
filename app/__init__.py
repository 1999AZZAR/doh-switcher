from flask import Flask
from flask_socketio import SocketIO
from flasgger import Swagger
import logging
import os

socketio = SocketIO()

def create_app():
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object('config')
    app.secret_key = app.config['SECRET_KEY']
    
    # Initialize extensions
    Swagger(app)
    socketio.init_app(app)
    
    # Configure logging
    log_file = app.config['LOG_FILE']
    log_dir = os.path.dirname(log_file)
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception as e:
            print(f"Error creating log directory {log_dir}: {e}")
    
    logging.basicConfig(
        filename=log_file,
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    
    # Initialize database
    from app.services.database import init_db
    with app.app_context():
        init_db()
    
    # Register routes
    from app.routes import register_routes
    register_routes(app)
    
    # Start background task
    from app.services.monitoring import background_thread
    socketio.start_background_task(background_thread)
    
    return app
