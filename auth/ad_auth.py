# auth/ad_auth.py
"""
Active Directory Authentication Module
Handles user authentication and authorization
"""

from ldap3 import Server, Connection, ALL, SIMPLE, SUBTREE
import ldap3.core.exceptions
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config

# --- START: Local Admin Configuration ---
LOCAL_ADMIN_USERNAME = 'production_portal_admin'
LOCAL_ADMIN_PASSWORD_HASH = 'pbkdf2:sha256:1000000$WJGhv0S4168kLXQq$de28edda0e790db12bc141a1bb3d6fa95eafe66d0c31c9ad8213d3f5d5f117db'
# --- END: Local Admin Configuration ---

def get_user_groups(username):
    """Get AD groups for a user using the service account"""
    if username == LOCAL_ADMIN_USERNAME:
        return {
            'groups': ['LocalAdmin'],
            'display_name': 'Local Portal Admin',
            'email': 'local_admin@system.local'
        }
    try:
        server = Server(Config.AD_SERVER, port=Config.AD_PORT, get_info=ALL)
        service_user = f'{Config.AD_SERVICE_ACCOUNT}@{Config.AD_DOMAIN}'

        service_conn = Connection(
            server,
            user=service_user,
            password=Config.AD_SERVICE_PASSWORD,
            authentication=SIMPLE,
            auto_bind=True
        )

        search_filter = f'(&(objectClass=user)(sAMAccountName={username}))'
        service_conn.search(
            Config.AD_BASE_DN,
            search_filter,
            SUBTREE,
            attributes=['memberOf', 'displayName', 'mail', 'distinguishedName', 'sAMAccountName']
        )

        if service_conn.entries:
            user_entry = service_conn.entries[0]

            groups = []
            if hasattr(user_entry, 'memberOf') and user_entry.memberOf:
                for group_dn in user_entry.memberOf:
                    group_name = str(group_dn).split(',')[0].replace('CN=', '')
                    groups.append(group_name)

            display_name = str(user_entry.displayName) if hasattr(user_entry, 'displayName') else username
            email = str(user_entry.mail) if hasattr(user_entry, 'mail') else f'{username}@{Config.AD_DOMAIN}'

            service_conn.unbind()

            return {
                'groups': groups,
                'display_name': display_name,
                'email': email
            }

        service_conn.unbind()
        return None

    except Exception as e:
        print(f"Error getting user groups: {str(e)}")
        return None

def authenticate_user(username, password):
    """Authenticate user against Active Directory OR local admin credentials"""

    # --- START: Check for Local Admin ---
    if username == LOCAL_ADMIN_USERNAME and check_password_hash(LOCAL_ADMIN_PASSWORD_HASH, password):
        print(f"Authenticated local admin: {username}")
        # Grant all admin permissions
        return {
            'username': LOCAL_ADMIN_USERNAME,
            'display_name': 'Local Portal Admin',
            'email': 'local_admin@system.local',
            'groups': ['LocalAdmin'],
            'is_admin': True, # Downtime Admin
            'is_user': True,
            'is_scheduling_admin': True, # Scheduling Admin
            'is_scheduling_user': True,
            'is_portal_admin': True, # Flag for the new group type (optional but good practice)
        }
    # --- END: Check for Local Admin ---

    # Test mode for development
    if Config.TEST_MODE:
        test_users = {
            # ... (test users remain the same) ...
             'dt_admin': {
                'password': 'password', 'display_name': 'Downtime Admin',
                'groups': [Config.AD_ADMIN_GROUP]
            },
            'dt_user': {
                'password': 'password', 'display_name': 'Downtime User',
                'groups': [Config.AD_USER_GROUP]
            },
            'sched_admin': {
                'password': 'password', 'display_name': 'Scheduling Admin',
                'groups': [Config.AD_SCHEDULING_ADMIN_GROUP]
            },
            'sched_user': {
                'password': 'password', 'display_name': 'Scheduling User',
                'groups': [Config.AD_SCHEDULING_USER_GROUP]
            },
            'super_admin': {
                'password': 'password', 'display_name': 'Super Admin',
                'groups': [Config.AD_ADMIN_GROUP, Config.AD_SCHEDULING_ADMIN_GROUP]
            },
            # Add a test user for the new portal admin if needed
            'portal_admin': {
                'password': 'password', 'display_name': 'Portal Admin (Test)',
                'groups': [Config.AD_PORTAL_ADMIN_GROUP]
            }
        }

        if username in test_users and test_users[username]['password'] == password:
            user = test_users[username]
            # --- START: Check for new Portal Admin group in TEST MODE ---
            is_portal_admin = Config.AD_PORTAL_ADMIN_GROUP in user['groups']
            # If portal admin, grant all permissions
            is_admin = Config.AD_ADMIN_GROUP in user['groups'] or is_portal_admin
            is_user = Config.AD_USER_GROUP in user['groups'] or is_portal_admin
            is_scheduling_admin = Config.AD_SCHEDULING_ADMIN_GROUP in user['groups'] or is_portal_admin
            is_scheduling_user = Config.AD_SCHEDULING_USER_GROUP in user['groups'] or is_portal_admin
            # --- END: Check for new Portal Admin group in TEST MODE ---

            # User must be in at least one relevant group (or be portal admin)
            if not any([is_admin, is_user, is_scheduling_admin, is_scheduling_user]):
                 return None

            return {
                'username': username,
                'display_name': user['display_name'],
                'email': f'{username}@{Config.AD_DOMAIN}',
                'groups': user['groups'],
                'is_admin': is_admin,
                'is_user': is_user,
                'is_scheduling_admin': is_scheduling_admin,
                'is_scheduling_user': is_scheduling_user,
                'is_portal_admin': is_portal_admin, # Add the flag
            }
        # If not local admin and not a test user in test mode, return None
        return None

    # Real AD Authentication
    try:
        server = Server(Config.AD_SERVER, port=Config.AD_PORT, get_info=ALL)
        user_principal = f'{username}@{Config.AD_DOMAIN}'

        try:
            # Attempt user authentication
            user_conn = Connection(
                server,
                user=user_principal,
                password=password,
                authentication=SIMPLE,
                auto_bind=True
            )
            user_conn.unbind()

            # Get user groups
            user_info = get_user_groups(username)

            if user_info:
                # --- START: Check for new Portal Admin group in AD ---
                is_portal_admin = Config.AD_PORTAL_ADMIN_GROUP in user_info['groups']

                # Determine permissions based on groups
                is_in_admin = Config.AD_ADMIN_GROUP in user_info['groups'] or is_portal_admin
                is_in_user = Config.AD_USER_GROUP in user_info['groups'] or is_portal_admin
                is_in_scheduling_admin = Config.AD_SCHEDULING_ADMIN_GROUP in user_info['groups'] or is_portal_admin
                is_in_scheduling_user = Config.AD_SCHEDULING_USER_GROUP in user_info['groups'] or is_portal_admin
                # --- END: Check for new Portal Admin group in AD ---

                # User must be in at least one relevant group (or be portal admin)
                if not any([is_in_admin, is_in_user, is_in_scheduling_admin, is_in_scheduling_user]):
                    print(f"User {username} not in required AD groups")
                    return None

                return {
                    'username': username,
                    'display_name': user_info['display_name'],
                    'email': user_info['email'],
                    'groups': user_info['groups'],
                    'is_admin': is_in_admin,
                    'is_user': is_in_user,
                    'is_scheduling_admin': is_in_scheduling_admin,
                    'is_scheduling_user': is_in_scheduling_user,
                    'is_portal_admin': is_portal_admin, # Add the flag
                }

        except ldap3.core.exceptions.LDAPBindError:
            print(f"Invalid AD credentials for user: {username}")
            return None # Failed AD auth, and wasn't local admin

    except Exception as e:
        print(f"AD Authentication error: {str(e)}")
        # If AD is unavailable, this will likely fail, but local admin check happened first.
        return None

    # Fallback if AD auth somehow fails without exception but didn't match local admin
    return None

# --- Functions below need updating ---

def require_login(session):
    """Check if user is logged in"""
    return 'user' in session

def require_admin(session):
    """Check if user is DowntimeTracker_Admin, Production_Portal_Admin OR local admin"""
    if 'user' in session:
        # Check local admin OR portal admin flag OR specific group flag
        return (session['user'].get('username') == LOCAL_ADMIN_USERNAME or
                session['user'].get('is_portal_admin', False) or
                session['user'].get('is_admin', False))
    return False

def require_user(session):
    """Check if user is DowntimeTracker_User, Production_Portal_Admin OR local admin"""
    if 'user' in session:
        # Local admin and portal admin have user permissions too
        return (session['user'].get('username') == LOCAL_ADMIN_USERNAME or
                session['user'].get('is_portal_admin', False) or
                session['user'].get('is_user', False))
    return False

def require_scheduling_admin(session):
    """Check if user is Scheduling_Admin, Production_Portal_Admin OR local admin"""
    if 'user' in session:
        # Local admin and portal admin have scheduling admin permissions too
        return (session['user'].get('username') == LOCAL_ADMIN_USERNAME or
                session['user'].get('is_portal_admin', False) or
                session['user'].get('is_scheduling_admin', False))
    return False

def require_scheduling_user(session):
    """Check if user is Scheduling_User, Production_Portal_Admin OR local admin"""
    if 'user' in session:
        # Local admin and portal admin have scheduling user permissions too
        return (session['user'].get('username') == LOCAL_ADMIN_USERNAME or
                session['user'].get('is_portal_admin', False) or
                session['user'].get('is_scheduling_user', False))
    return False

def test_ad_connection():
    """Test Active Directory connection"""
    if Config.TEST_MODE:
        return True

    try:
        server = Server(Config.AD_SERVER, port=Config.AD_PORT, get_info=ALL)
        service_user = f'{Config.AD_SERVICE_ACCOUNT}@{Config.AD_DOMAIN}'

        conn = Connection(
            server,
            user=service_user,
            password=Config.AD_SERVICE_PASSWORD,
            authentication=SIMPLE,
            auto_bind=True
        )
        conn.unbind()
        return True
    except Exception as e:
        print(f"AD connection test failed: {str(e)}")
        return False