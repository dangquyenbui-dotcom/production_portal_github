# app.py - UPDATED to include PO Blueprint and Auth Helpers in Jinja
# *** ADDED DETAILED LOGGING FOR LDAP3 ***
# *** REMOVED Config.AD_DOMAIN reference ***
# *** ADDED SSL Context handling for app.run ***

"""
Production Portal - Main Application
Production-ready configuration with network access and i18n support
"""

# *** START: Added Logging Configuration ***
import logging
import sys
# Configure root logger to output to console
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# Set ldap3 library logger to DEBUG level for detailed output
# ldap3_logger = logging.getLogger('ldap3') # Comment out if not needed for Azure AD debugging
# ldap3_logger.setLevel(logging.DEBUG)        # Comment out if not needed for Azure AD debugging
# *** END: Added Logging Configuration ***

from flask import Flask, session
import os
from datetime import timedelta
from config import Config
import socket
import ssl # <-- Import ssl module

# Import i18n configuration
from i18n_config import I18nConfig, _, format_datetime_i18n, format_date_i18n
# --- MODIFIED: Import Azure AD/MSAL based auth helpers ---
from auth import (
    require_login,
    require_admin,
    require_user,
    require_scheduling_admin,
    require_scheduling_user
    # Note: test_ad_connection might be removed or return True if kept
)

def create_app():
    app = Flask(__name__)

    # Configuration
    app.secret_key = Config.SECRET_KEY
    app.permanent_session_lifetime = timedelta(hours=Config.SESSION_HOURS)

    # Configure static files path
    app.static_folder = 'static'
    app.static_url_path = '/static'

    # Initialize internationalization
    I18nConfig.init_app(app)

    # Register template filters for i18n
    app.jinja_env.filters['datetime_i18n'] = format_datetime_i18n
    app.jinja_env.filters['date_i18n'] = format_date_i18n

    # --- Make translation and AUTH functions available in templates ---
    app.jinja_env.globals['_'] = _
    app.jinja_env.globals['get_locale'] = lambda: session.get('language', 'en')
    app.jinja_env.globals['get_languages'] = I18nConfig.get_available_languages
    app.jinja_env.globals['require_admin'] = require_admin
    app.jinja_env.globals['require_user'] = require_user
    app.jinja_env.globals['require_scheduling_admin'] = require_scheduling_admin
    app.jinja_env.globals['require_scheduling_user'] = require_scheduling_user
    # --- END making functions available ---

    # Register blueprints
    register_blueprints(app)

    # Initialize database
    initialize_database()

    return app

# ***** ENSURE THIS FUNCTION IS CORRECT *****
def register_blueprints(app):
    """Register all application blueprints"""
    from routes.main import main_bp
    from routes.downtime import downtime_bp
    from routes.erp_routes import erp_bp
    from routes.scheduling import scheduling_bp
    from routes.reports import reports_bp # <-- Ensure this is imported
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
    # --- ADDED: Import Permissions Blueprint ---
    from routes.admin.permissions import admin_permissions_bp

    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(downtime_bp)
    app.register_blueprint(erp_bp)
    app.register_blueprint(scheduling_bp)
    app.register_blueprint(reports_bp) # <-- Ensure this is registered (prefix is in reports.py)
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
    # --- ADDED: Register Permissions Blueprint ---
    app.register_blueprint(admin_permissions_bp, url_prefix='/admin')
# ***** END ENSURE THIS FUNCTION IS CORRECT *****


def initialize_database():
    """Initialize database connection and verify tables"""
    from database.connection import DatabaseConnection

    db = DatabaseConnection()
    if db.test_connection():
        print("✅ Database: Connected and ready!") #
    else:
        print("❌ Database: Connection failed!") #
        print("   Run database initialization script") #

def get_local_ip():
    """Get the local IP address of the machine"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #
        # Try connecting to an external server to find the local IP used for external comms
        s.connect(("8.8.8.8", 80)) # Google's public DNS
        local_ip = s.getsockname()[0] #
        s.close() #
        return local_ip
    except Exception:
        try:
            # Fallback: Get hostname and resolve it
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            return local_ip
        except Exception:
             # Final fallback
            return "127.0.0.1" #

def test_services():
    """Test all service connections on startup"""
    print("\n" + "="*60) #
    print(f"PRODUCTION PORTAL v{Config.APP_VERSION if hasattr(Config, 'APP_VERSION') else '?.?.?'} - STARTUP DIAGNOSTICS") # Use version if exists
    print("="*60) #

    from database.connection import DatabaseConnection #
    db = DatabaseConnection() #
    if db.test_connection(): #
        print("✅ Database: Connected") #
    else:
        print("❌ Database: Not connected") #

    # --- AD Connection Test is no longer relevant with Azure AD ---
    # if not Config.TEST_MODE: #
    #     from auth import test_ad_connection # This function might be removed from auth now
    #     if test_ad_connection(): #
    #         print("✅ Active Directory: Connected") #
    #     else:
    #         print("❌ Active Directory: Not connected") #
    if Config.TEST_MODE:
        print("🧪 Test Mode: Using fake authentication") #
    else:
        print("ℹ️ Authentication Mode: Azure AD (OIDC)")


    print("="*60 + "\n") #

if __name__ == '__main__':
    # Validate configuration first
    if not Config.validate():
        print("❌ Configuration validation failed. Please check your .env file.")
        sys.exit(1) # Exit if config is invalid

    # Ensure directories exist
    os.makedirs('static', exist_ok=True) #
    os.makedirs('templates', exist_ok=True) #

    local_ip = get_local_ip() #

    # Print Configuration Summary
    print("\n" + "="*50) #
    print(f"PRODUCTION PORTAL v{Config.APP_VERSION if hasattr(Config, 'APP_VERSION') else '?.?.?'} - CONFIGURATION") # Use version if exists
    print("="*50) #
    print(f"Mode: {'TEST' if Config.TEST_MODE else 'PRODUCTION'}") #
    print(f"Database: {Config.DB_SERVER}/{Config.DB_NAME}") #
    # *** COMMENTED OUT problematic line ***
    # print(f"AD Domain: {Config.AD_DOMAIN}") # AD_DOMAIN no longer exists in Config
    print(f"Auth Mode: {'Test' if Config.TEST_MODE else 'Azure AD'}") # Indicate Auth mode
    if not Config.TEST_MODE:
        print(f"AAD Tenant ID: {Config.AAD_TENANT_ID}")
        print(f"AAD Client ID: {Config.AAD_CLIENT_ID}")
    print(f"HTTPS Enabled: {'Yes' if Config.SSL_ENABLED else 'No'}") # <-- Indicate HTTPS status
    if Config.SSL_ENABLED:
        print(f"  Cert Path: {Config.SSL_CERT_PATH}")
        print(f"  Key Path: {Config.SSL_KEY_PATH}")
    print(f"Languages: English, Spanish") #
    print("="*50 + "\n") #

    # Run connection tests
    test_services() #

    # Create Flask App
    app = create_app() #

    # --- Setup SSL Context if enabled ---
    ssl_context = None
    protocol = "http"
    if Config.SSL_ENABLED:
        try:
            # Using 'adhoc' might work for simple dev certs, but explicit paths are better
            # For production/signed certs:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(Config.SSL_CERT_PATH, Config.SSL_KEY_PATH)
            ssl_context = context
            protocol = "https"
            print("✅ SSL Context created successfully.")
        except Exception as e:
            print(f"❌ Error creating SSL context: {e}")
            print("   Falling back to HTTP.")
            # Optionally exit if HTTPS is mandatory:
            # sys.exit(1)

    # --- Print Server Access URLs ---
    print("\n" + "="*60) #
    print(f"🚀 SERVER STARTING ({protocol.upper()}) - ACCESS URLS:") #
    print("="*60) #
    print(f"Local:        {protocol}://localhost:5000") #
    print(f"Network:      {protocol}://{local_ip}:5000") #
    print("="*60) #
    print("\n📝 Make sure:") #
    print(f"  1. Firewall allows port 5000 (TCP)") #
    print("  2. No antivirus blocking the connection") #
    if protocol == "https":
        print("  3. Your browser trusts the certificate (or bypass warnings for dev certs)")
    print("\nPress CTRL+C to stop the server\n") #

    # --- Run the Flask development server ---
    # Use Waitress for a more production-ready server than Flask's built-in one
    # If using Waitress with SSL, it needs configuration differently.
    # Sticking with app.run for simplicity based on the current structure.
    app.run( #
        host='0.0.0.0', # Listen on all network interfaces
        port=5000, # Standard Flask dev port
        debug=True, # Enables detailed error messages and auto-reloading
        ssl_context=ssl_context # Pass the SSL context here
    )