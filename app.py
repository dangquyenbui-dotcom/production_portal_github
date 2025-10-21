# app.py - Enabling FULL DEBUG MODE for Flask/Werkzeug

"""
Production Portal - Main Application
Production-ready configuration with network access and i18n support
"""

import logging
import sys
# Configure root logger - Flask's debug mode often handles this, but setting explicitly
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Set Werkzeug logger to DEBUG ---
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.DEBUG)
# --- End Werkzeug Logger Setting ---


from flask import Flask, session, current_app # Added current_app for logger
import os
from datetime import timedelta
from config import Config
import socket
import ssl

# Import i18n configuration
from i18n_config import I18nConfig, _, format_datetime_i18n, format_date_i18n
# Import Auth helpers
from auth import (
    require_login,
    require_admin,
    require_user,
    require_scheduling_admin,
    require_scheduling_user
)
from database import sessions_db # Import sessions_db needed for validate_session

# --- Session Validation Decorator ---
from functools import wraps
from flask import request, redirect, url_for, flash

def validate_session(f):
    """Decorator to validate session on each request"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_app.logger.debug(f"Validating session for endpoint: {request.endpoint}")
        exempt_endpoints = ['main.login', 'main.login_microsoft', 'main.authorized', 'main.logout', 'static']
        if request.endpoint in exempt_endpoints:
             current_app.logger.debug(f"Endpoint {request.endpoint} is exempt from session validation.")
             return f(*args, **kwargs)

        if 'user' in session and 'session_id' in session:
            current_app.logger.debug(f"User and session_id found in session. Validating session {session['session_id']} for user {session['user'].get('username')}")
            if not sessions_db.validate_session(session['session_id'], session['user']['username']):
                current_app.logger.warning(f"Session validation failed for session_id {session.get('session_id')}. Clearing session.")
                session.clear()
                flash(_('Your session has expired or you logged in from another location'), 'error')
                return redirect(url_for('main.login'))
            current_app.logger.debug("Session is valid.")
        elif 'user' not in session:
             current_app.logger.info(f"No user found in session for protected endpoint {request.endpoint}. Redirecting to login.")
             flash(_('Please log in to access this page.'), 'info')
             return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function
# --- End Session Validation Decorator ---


def create_app():
    app = Flask(__name__)

    # --- Set Flask app logger level ---
    app.logger.setLevel(logging.DEBUG)
    app.logger.info("Flask logger set to DEBUG level.")
    # --- End Flask Logger Setting ---


    # Configuration
    app.secret_key = Config.SECRET_KEY
    app.permanent_session_lifetime = timedelta(hours=Config.SESSION_HOURS)
    app.static_folder = 'static'
    app.static_url_path = '/static'

    # Initialize internationalization
    I18nConfig.init_app(app)

    # Register template filters & globals
    app.jinja_env.filters['datetime_i18n'] = format_datetime_i18n
    app.jinja_env.filters['date_i18n'] = format_date_i18n
    app.jinja_env.globals['_'] = _
    app.jinja_env.globals['get_locale'] = lambda: session.get('language', I18nConfig.DEFAULT_LANGUAGE)
    app.jinja_env.globals['get_languages'] = I18nConfig.get_available_languages
    app.jinja_env.globals['require_admin'] = require_admin
    app.jinja_env.globals['require_user'] = require_user
    app.jinja_env.globals['require_scheduling_admin'] = require_scheduling_admin
    app.jinja_env.globals['require_scheduling_user'] = require_scheduling_user

    # Register blueprints
    register_blueprints(app)

    # Initialize database
    initialize_database()

    app.logger.info("Flask app created successfully.")
    return app

# Blueprint registration (remains the same)
def register_blueprints(app):
    """Register all application blueprints"""
    app.logger.debug("Registering blueprints...")
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

    # Register blueprints
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

    # Register all admin blueprints under the /admin prefix
    app.register_blueprint(admin_panel_bp, url_prefix='/admin')
    app.register_blueprint(admin_facilities_bp, url_prefix='/admin')
    app.register_blueprint(admin_lines_bp, url_prefix='/admin')
    app.register_blueprint(admin_categories_bp, url_prefix='/admin')
    app.register_blueprint(admin_audit_bp, url_prefix='/admin')
    app.register_blueprint(admin_shifts_bp, url_prefix='/admin')
    app.register_blueprint(admin_users_bp, url_prefix='/admin')
    app.register_blueprint(admin_capacity_bp, url_prefix='/admin')
    app.logger.debug("Blueprints registered.")


def initialize_database():
    """Initialize database connection and verify tables"""
    from database.connection import get_db
    from database.erp_connection_base import get_erp_db_connection
    print("Attempting to initialize databases...") # Keep as print for early startup info
    try:
        local_db = get_db()
        if local_db and local_db.test_connection():
            print("✅ Local Database: Connected and basic check passed.")
        else:
            print("❌ Local Database: Connection failed or check failed.")
    except Exception as e:
        print(f"❌ Local Database: Error during initialization: {e}")

    try:
        erp_conn = get_erp_db_connection()
        if erp_conn and erp_conn.connection:
             print("✅ ERP Database: Connection successful on initialization.")
        else:
            print("❌ ERP Database: Connection failed during initialization.")
    except Exception as e:
        print(f"❌ ERP Database: Error during initialization: {e}")


def get_local_ip():
    """Get the local IP address of the machine"""
    # This function remains the same
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            return local_ip
        except Exception:
            return "127.0.0.1"

if __name__ == '__main__':
    # Ensure directories exist
    os.makedirs('static', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    os.makedirs('instance', exist_ok=True)

    local_ip = get_local_ip()

    # Validate config
    if not Config.validate():
        print("❌ Exiting due to configuration errors.")
        sys.exit(1)
    else:
        print("✅ Configuration validated successfully.")

    # Print Configuration Summary
    print("\n" + "="*50)
    print("PRODUCTION PORTAL - CONFIGURATION")
    print("="*50)
    print(f"Mode: {'TEST' if Config.TEST_MODE else 'PRODUCTION'}")
    print(f"Local DB: {Config.DB_SERVER}/{Config.DB_NAME}")
    print(f"ERP DB: {Config.ERP_DB_SERVER}/{Config.ERP_DB_NAME}")
    print(f"Auth Mode: {'Test/Local Admin' if Config.TEST_MODE else 'Azure AD'}")
    if not Config.TEST_MODE:
        print(f"AAD Tenant ID: {Config.AAD_TENANT_ID}")
        print(f"AAD Client ID: {Config.AAD_CLIENT_ID}")
    print(f"Languages: {', '.join(I18nConfig.LANGUAGES.keys())}")
    print(f"SSL Cert: {Config.SSL_CERT_PATH}")
    print(f"SSL Key: {Config.SSL_KEY_PATH}")
    print("="*50 + "\n")

    # Create Flask App
    app = create_app()

    # Check if SSL files exist
    ssl_cert_exists = os.path.exists(Config.SSL_CERT_PATH)
    ssl_key_exists = os.path.exists(Config.SSL_KEY_PATH)
    context = None
    protocol = "http"

    if ssl_cert_exists and ssl_key_exists:
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(Config.SSL_CERT_PATH, Config.SSL_KEY_PATH)
            protocol = "https"
            app.logger.info("✅ SSL context loaded successfully for app.run.")
        except Exception as e:
            app.logger.error(f"❌ Failed to load SSL context: {e}", exc_info=True)
            app.logger.warning("   Ensure SSL_CERT_PATH and SSL_KEY_PATH in .env are correct.")
            app.logger.warning("   Falling back to HTTP...")
            context = None
            protocol = "http"
    else:
        app.logger.warning("WARNING: SSL certificate or key not found. Serving HTTP...")
        protocol = "http"

    host = '0.0.0.0'
    port = 5000

    print("\n" + "="*60)
    # --- Indicate DEBUG MODE ON ---
    print(f"🚀 SERVER STARTING ({protocol.upper()}) using Flask Development Server (!!! DEBUG MODE ON !!!, Threaded):")
    print("="*60)
    print(f"Local:        {protocol}://localhost:{port}")
    print(f"Network:      {protocol}://{local_ip}:{port}")
    print("="*60)
    print("\n📝 Make sure:")
    print(f"  1. Firewall allows port {port}")
    print("  2. No antivirus blocking the connection")
    if protocol == "https":
        print("  3. Your browser may warn about the self-signed certificate. Proceed if expected.")
    # --- Updated Warning ---
    print("\n🔥🔥🔥 WARNING: Running in DEBUG MODE. Verbose logging enabled. Expect instability. NOT for production. 🔥🔥🔥")
    print("\nPress CTRL+C to stop the server\n")

    # --- Run using Flask's built-in server, enable debug, enable threaded ---
    app.run(
        host=host,
        port=port,
        debug=True,          # <-- SET BACK TO TRUE FOR DEBUGGING
        ssl_context=context, # Pass the SSL context if loaded
        threaded=True        # Keep threaded=True
    )
    # --- END MODIFICATION ---