# app.py - ADDED more detailed startup logging

import logging
# --- ADDED: Import for file logging ---
from logging.handlers import RotatingFileHandler
# --- END ADDED ---
from flask import Flask, session
import os
from datetime import timedelta
from config import Config
import socket

# ... (other imports remain the same) ...
from i18n_config import I18nConfig, _, format_datetime_i18n, format_date_i18n
from auth import (
    require_admin,
    require_user,
    require_scheduling_admin,
    require_scheduling_user
)
# **** Import test_ad_connection here ****
from auth import test_ad_connection
# **** Import DatabaseConnection here ****
from database.connection import DatabaseConnection


def create_app():
    app = Flask(__name__)

    # Configuration
    app.secret_key = Config.SECRET_KEY
    app.permanent_session_lifetime = timedelta(hours=Config.SESSION_HOURS)

    # Configure static files path
    app.static_folder = 'static'
    app.static_url_path = '/static'

    # --- MODIFIED: Robust Logging Configuration ---
    # Remove the basicConfig, we will configure handlers directly
    # logging.basicConfig(level=logging.INFO, ...) 

    log_level = logging.DEBUG # Set to DEBUG as requested
    
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.mkdir('logs')

    # File Handler (logs to portal.log)
    # Rotates at 5MB, keeps 10 backup logs.
    file_handler = RotatingFileHandler(
        'logs/portal.log', 
        maxBytes=5242880, 
        backupCount=10,
        encoding='utf-8' # --- ADDED: Specify encoding ---
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(log_level)

    # Console Handler (so you still see logs in the .bat window)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s'
    ))
    console_handler.setLevel(log_level)

    # Get the root logger
    app.logger.handlers = [] # Clear default handlers
    root_logger = logging.getLogger()
    root_logger.handlers = [] # Clear any existing root handlers
    
    # Add our new handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    root_logger.setLevel(log_level)
    
    # Also set Flask's logger level
    app.logger.setLevel(log_level)
    
    app.logger.info('--- Application Starting Up ---')
    # --- END MODIFIED ---

    # Initialize internationalization
    I18nConfig.init_app(app)

    # Register template filters for i18n
    app.jinja_env.filters['datetime_i18n'] = format_datetime_i18n
    app.jinja_env.filters['date_i18n'] = format_date_i18n

    # Make functions available in templates
    app.jinja_env.globals['_'] = _
    app.jinja_env.globals['get_locale'] = lambda: session.get('language', 'en')
    app.jinja_env.globals['get_languages'] = I18nConfig.get_available_languages
    app.jinja_env.globals['require_admin'] = require_admin
    app.jinja_env.globals['require_user'] = require_user
    app.jinja_env.globals['require_scheduling_admin'] = require_scheduling_admin
    app.jinja_env.globals['require_scheduling_user'] = require_scheduling_user

    # Register blueprints
    register_blueprints(app)

    # Initialize database
    initialize_database()

    app.logger.info('Flask app created and configured.')

    return app

# ... (register_blueprints function remains the same) ...
def register_blueprints(app):
    """Register all application blueprints"""
    from routes.main import main_bp
    from routes.downtime import downtime_bp
    from routes.erp_routes import erp_bp
    from routes.scheduling import scheduling_bp
    from routes.reports import reports_bp
    from routes.bom import bom_bp
    from routes.po import po_bp
    from routes.mrp import mrp_bp
    from routes.sales import sales_bp
    from routes.jobs import jobs_bp
    from routes.admin.panel import admin_panel_bp
    from routes.admin.facilities import admin_facilities_bp
    from routes.admin.production_lines import admin_lines_bp
    from routes.admin.categories import admin_categories_bp
    from routes.admin.audit import admin_audit_bp
    from routes.admin.shifts import admin_shifts_bp
    from routes.admin.users import admin_users_bp
    from routes.admin.capacity import admin_capacity_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(downtime_bp)
    app.register_blueprint(erp_bp)
    app.register_blueprint(scheduling_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(bom_bp)
    app.register_blueprint(po_bp)
    app.register_blueprint(mrp_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(admin_panel_bp, url_prefix='/admin')
    app.register_blueprint(admin_facilities_bp, url_prefix='/admin')
    app.register_blueprint(admin_lines_bp, url_prefix='/admin')
    app.register_blueprint(admin_categories_bp, url_prefix='/admin')
    app.register_blueprint(admin_audit_bp, url_prefix='/admin')
    app.register_blueprint(admin_shifts_bp, url_prefix='/admin')
    app.register_blueprint(admin_users_bp, url_prefix='/admin')
    app.register_blueprint(admin_capacity_bp, url_prefix='/admin')

def initialize_database():
    """Initialize database connection and verify tables"""
    # **** Use logger instead of print ****
    logging.info("Initializing local database connection...")
    db = DatabaseConnection() # Creates the first connection attempt
    if db.test_connection():
        logging.info("✅ Local Database: Connected and ready!")
    else:
        logging.error("❌ Local Database: Connection failed!")
        logging.warning("   Run database initialization script if needed.")

def get_local_ip():
    """Get the local IP address of the machine"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "127.0.0.1"

# **** MODIFIED test_services with more logging ****
def test_services():
    """Test all service connections on startup"""
    logging.info("\n" + "="*60)
    logging.info("PRODUCTION PORTAL - STARTUP DIAGNOSTICS")
    logging.info("="*60)

    # Local DB Test
    logging.info("Testing Local DB connection...")
    db = DatabaseConnection() # Get the instance (should exist from initialize_database)
    if db.test_connection():
        logging.info("✅ Local Database: Connected")
    else:
        logging.error("❌ Local Database: Not connected")

    # AD Test (only if not in TEST_MODE)
    if not Config.TEST_MODE:
        logging.info("Testing Active Directory connection...")
        if test_ad_connection():
            logging.info("✅ Active Directory: Connected")
        else:
            # **** Changed to ERROR level ****
            logging.error("❌ Active Directory: Not connected (Check AD_SERVER, credentials in .env)")
    else:
        logging.warning("🧪 Test Mode: Skipping AD connection test.")

    # ERP DB Test (Optional but good)
    try:
        logging.info("Testing ERP DB connection...")
        from database.erp_connection_base import get_erp_db_connection
        erp_conn = get_erp_db_connection() # This will attempt connection if not already made
        if erp_conn and erp_conn.connection:
             logging.info("✅ ERP Database: Connection successful (via initial check or test)")
        else:
             logging.error("❌ ERP Database: Connection failed (Check ERP_DB_* settings in .env)")
    except Exception as e:
        logging.error(f"❌ ERP Database: Connection test failed with error: {e}")


    logging.info("="*60 + "\n")
# **** END MODIFIED test_services ****

if __name__ == '__main__':
    # --- MODIFIED: Setup logging for startup process itself ---
    # This configures logging *before* the app is created,
    # capturing startup messages.
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(name)s : %(message)s')
    # --- END MODIFIED ---

    os.makedirs('static', exist_ok=True)
    os.makedirs('templates', exist_ok=True)

    local_ip = get_local_ip()

    logging.info("\n" + "="*50)
    logging.info(f"PRODUCTION PORTAL v{os.environ.get('APP_VERSION', '?.?.?')}") # Add version if you set it
    logging.info("="*50)
    logging.info(f"Mode: {'TEST' if Config.TEST_MODE else 'PRODUCTION'}")
    logging.info(f"Local DB: {Config.DB_SERVER}/{Config.DB_NAME}")
    logging.info(f"ERP DB: {Config.ERP_DB_SERVER}/{Config.ERP_DB_NAME}")
    logging.info(f"AD Domain: {Config.AD_DOMAIN if not Config.TEST_MODE else 'N/A (Test Mode)'}")
    logging.info(f"Languages: English, Spanish")
    logging.info("="*50 + "\n")

    # Initialize Local DB connection early
    initialize_database()

    # Run connection tests
    test_services()

    # Create Flask App (after initial DB setup)
    logging.info("Creating Flask app instance...")
    app = create_app()
    logging.info("Flask app instance created.")


    logging.info("\n" + "="*60)
    logging.info("🚀 SERVER STARTING (HTTP via Waitress) - ACCESS URLS:")
    logging.info("="*60)
    logging.info(f"Local:        http://localhost:5000")
    logging.info(f"Network:      http://{local_ip}:5000")
    logging.info("="*60)
    logging.info("\n📝 Make sure:")
    logging.info("  1. Windows Firewall allows port 5000")
    logging.info("  2. No antivirus blocking the connection")
    logging.info("\nPress CTRL+C to stop the server\n")

    # Use Waitress for serving
    try:
        from waitress import serve
        # **** Add logging before serve call ****
        logging.info("Starting Waitress server...")
        serve(app, host='0.0.0.0', port=5000)
    except Exception as e:
        logging.exception(f"FATAL: Failed to start Waitress server: {e}") # Log exception traceback