# config.py
"""
Configuration settings for Production Portal
Reads sensitive information from environment variables
*** ADDED import os ***
*** MODIFIED AAD_SCOPES default ***
"""

import os # <-- Ensure this is still here
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration"""

    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
    SESSION_HOURS = int(os.getenv('SESSION_HOURS', '8'))

    # --- Remove or comment out old AD vars ---
    # AD_SERVER = os.getenv('AD_SERVER')
    # ... (etc.)

    # --- Add Azure AD / MSAL Config ---
    AAD_CLIENT_ID = os.getenv('AAD_CLIENT_ID')
    AAD_CLIENT_SECRET = os.getenv('AAD_CLIENT_SECRET')
    AAD_TENANT_ID = os.getenv('AAD_TENANT_ID')
    AAD_AUTHORITY = os.getenv('AAD_AUTHORITY', f"https://login.microsoftonline.com/{AAD_TENANT_ID}")
    # *** MODIFIED DEFAULT: Removed openid and profile ***
    _scopes_str = os.getenv('AAD_SCOPES', 'email User.Read')
    AAD_SCOPES = _scopes_str.split(' ') if _scopes_str else []

    # --- Keep Group Names (for mapping) ---
    AD_ADMIN_GROUP = os.getenv('AD_ADMIN_GROUP', 'DowntimeTracker_Admin')
    AD_USER_GROUP = os.getenv('AD_USER_GROUP', 'DowntimeTracker_User')
    AD_SCHEDULING_ADMIN_GROUP = os.getenv('AD_SCHEDULING_ADMIN_GROUP', 'Scheduling_Admin')
    AD_SCHEDULING_USER_GROUP = os.getenv('AD_SCHEDULING_USER_GROUP', 'Scheduling_User')
    AD_PORTAL_ADMIN_GROUP = os.getenv('AD_PORTAL_ADMIN_GROUP', 'Production_Portal_Admin')

    TEST_MODE = os.getenv('TEST_MODE', 'False').lower() == 'true'

    # --- Main Application Database (ProductionDB) ---
    DB_SERVER = os.getenv('DB_SERVER')
    DB_NAME = os.getenv('DB_NAME', 'ProductionDB')
    DB_USE_WINDOWS_AUTH = os.getenv('DB_USE_WINDOWS_AUTH', 'False').lower() == 'true'
    DB_USERNAME = os.getenv('DB_USERNAME')
    DB_PASSWORD = os.getenv('DB_PASSWORD')

    # --- ERP Database (Deacom) ---
    ERP_DB_SERVER = os.getenv('ERP_DB_SERVER')
    ERP_DB_NAME = os.getenv('ERP_DB_NAME')
    ERP_DB_USERNAME = os.getenv('ERP_DB_USERNAME')
    ERP_DB_PASSWORD = os.getenv('ERP_DB_PASSWORD')
    ERP_DB_PORT = os.getenv('ERP_DB_PORT', '1433')
    ERP_DB_DRIVER = os.getenv('ERP_DB_DRIVER', 'ODBC Driver 17 for SQL Server')
    ERP_DB_TIMEOUT = int(os.getenv('ERP_DB_TIMEOUT', '30'))

    # Email settings (Optional)
    SMTP_SERVER = os.getenv('SMTP_SERVER', 'mail.wepackitall.local')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
    SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', 'True').lower() == 'true'
    EMAIL_FROM = os.getenv('EMAIL_FROM', 'downtime@wepackitall.local')

    # Email notifications mapping (example, adjust as needed)
    EMAIL_NOTIFICATIONS = {
        'Mechanical': ['Maintenance Team', 'Facility Manager'],
        'Electrical': ['Maintenance Team', 'Facility Manager'],
        'Material Shortage': ['Supply Chain', 'Production Manager'],
        'Quality Hold': ['Quality Team', 'Production Manager'],
        'No Operator': ['HR Team', 'Production Manager'],
        'Changeover': ['Production Manager'],
        'Break Time': [],
        'Cleaning': ['Production Manager'],
        'Planned Maintenance': ['Maintenance Team'],
        'Other': ['Production Manager', 'Facility Manager']
    }

    @classmethod
    def validate(cls):
        """Validate required configuration"""
        errors = []
        # --- Remove old AD validation ---
        # if not cls.TEST_MODE:
        #     if not cls.AD_SERVER: errors.append("AD_SERVER is required") ...

        # --- Add Azure AD validation ---
        if not cls.AAD_CLIENT_ID: errors.append("AAD_CLIENT_ID is required")
        if not cls.AAD_CLIENT_SECRET: errors.append("AAD_CLIENT_SECRET is required")
        if not cls.AAD_TENANT_ID: errors.append("AAD_TENANT_ID is required")
        if not cls.AAD_AUTHORITY: errors.append("AAD_AUTHORITY is required")

        # --- DB validation ---
        if not cls.DB_SERVER: errors.append("DB_SERVER is required")
        if not cls.DB_USE_WINDOWS_AUTH:
            if not cls.DB_USERNAME: errors.append("DB_USERNAME is required when not using Windows Auth")
            if not cls.DB_PASSWORD: errors.append("DB_PASSWORD is required when not using Windows Auth")

        # --- ERP validation ---
        if not cls.ERP_DB_SERVER: errors.append("ERP_DB_SERVER is required")
        if not cls.ERP_DB_NAME: errors.append("ERP_DB_NAME is required")
        if not cls.ERP_DB_USERNAME: errors.append("ERP_DB_USERNAME is required")
        if not cls.ERP_DB_PASSWORD: errors.append("ERP_DB_PASSWORD is required")

        if errors:
            print("Configuration errors:")
            for error in errors:
                print(f"  - {error}")
            return False
        return True