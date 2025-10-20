# auth/ad_auth.py
"""
Active Directory Authentication Module
Handles user authentication and authorization
"""

from ldap3 import Server, Connection, ALL, SIMPLE, SUBTREE
import ldap3.core.exceptions
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
# --- ADD Database Import ---
from database.permissions import permissions_db # Make sure permissions_db is correctly imported elsewhere

# --- START: Local Admin Configuration ---
LOCAL_ADMIN_USERNAME = 'production_portal_admin'
# Ensure this hash matches what you intend
LOCAL_ADMIN_PASSWORD_HASH = 'pbkdf2:sha256:1000000$7GUCiDMbjttS4Sa9$87463836cef236308961cbf57d01a4cd1b14e79c7bbd707ff15faa6a947c1609'
# --- END: Local Admin Configuration ---

# <<< --- VERIFY THIS FUNCTION DEFINITION EXISTS AND IS SPELLED CORRECTLY --- >>>
def get_user_groups(username):
    """Get AD groups for a user using the service account"""
    if username == LOCAL_ADMIN_USERNAME:
        return {
            'groups': ['LocalAdmin'],
            'display_name': 'Local Portal Admin',
            'email': 'local_admin@system.local'
        }
    # --- Ensure AD Service Account is configured if not in Test Mode ---
    if not Config.AD_SERVICE_ACCOUNT or not Config.AD_SERVICE_PASSWORD:
        print("Warning: AD_SERVICE_ACCOUNT or AD_SERVICE_PASSWORD not configured. Cannot query AD groups.")
        # Return basic info without groups if service account is missing
        return {
            'groups': [],
            'display_name': username, # Default display name
            'email': f'{username}@{Config.AD_DOMAIN or "unknown.local"}' # Default email
        }

    try:
        server = Server(Config.AD_SERVER, port=Config.AD_PORT, get_info=ALL)
        # Construct the service user principal name correctly
        service_user = f'{Config.AD_SERVICE_ACCOUNT}@{Config.AD_DOMAIN}'

        # Use SIMPLE authentication for service account bind
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
            # Check if memberOf attribute exists and has values
            if hasattr(user_entry, 'memberOf') and user_entry.memberOf:
                # Iterate through the memberOf attribute values
                for group_dn in user_entry.memberOf.values: # Iterate through values if it's a list
                    # Extract the CN (Common Name) part of the group's Distinguished Name
                    # Example DN: CN=GroupName,OU=Groups,DC=yourdomain,DC=local
                    try:
                        # Find the first 'CN=' part
                        cn_part = str(group_dn).split(',')[0]
                        if cn_part.upper().startswith('CN='):
                             group_name = cn_part[3:] # Get the part after 'CN='
                             groups.append(group_name)
                    except Exception:
                        pass # Ignore parsing errors for specific group DNs

            # Safely get display name and email
            display_name = str(user_entry.displayName) if hasattr(user_entry, 'displayName') and user_entry.displayName else username
            email = str(user_entry.mail) if hasattr(user_entry, 'mail') and user_entry.mail else f'{username}@{Config.AD_DOMAIN or "unknown.local"}'

            service_conn.unbind()

            return {
                'groups': groups,
                'display_name': display_name,
                'email': email
            }
        else:
            print(f"User {username} not found in AD search.")
            service_conn.unbind()
            # Return basic info even if user not found, authentication might still work
            return {
                'groups': [],
                'display_name': username,
                'email': f'{username}@{Config.AD_DOMAIN or "unknown.local"}'
            }


    except ldap3.core.exceptions.LDAPSocketOpenError as e:
        print(f"LDAP Connection Error getting groups for {username}: Could not connect to AD server {Config.AD_SERVER}:{Config.AD_PORT}. Details: {e}")
        return None # Indicate connection failure
    except ldap3.core.exceptions.LDAPBindError as e:
         print(f"LDAP Bind Error getting groups for {username} using service account {service_user}: Check service account credentials. Details: {e}")
         return None # Indicate bind failure
    except Exception as e:
        import traceback
        print(f"Unexpected error getting user groups for {username}: {str(e)}")
        traceback.print_exc()
        return None # Indicate general failure

# <<< --- REST OF THE FILE (authenticate_user, permission checks, test_ad_connection) --- >>>
# ... (ensure the rest of the file provided previously is present) ...

def authenticate_user(username, password):
    """Authenticate user against Active Directory OR local admin credentials"""

    # --- Check for Local Admin ---
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
            'is_portal_admin': True, # Flag for the new group type
        }

    # Test mode for development
    if Config.TEST_MODE:
        test_users = {
            'dt_admin': {'password': 'password', 'display_name': 'Downtime Admin', 'groups': [Config.AD_ADMIN_GROUP]},
            'dt_user': {'password': 'password', 'display_name': 'Downtime User', 'groups': [Config.AD_USER_GROUP]},
            'sched_admin': {'password': 'password', 'display_name': 'Scheduling Admin', 'groups': [Config.AD_SCHEDULING_ADMIN_GROUP]},
            'sched_user': {'password': 'password', 'display_name': 'Scheduling User', 'groups': [Config.AD_SCHEDULING_USER_GROUP]},
            'super_admin': {'password': 'password', 'display_name': 'Super Admin', 'groups': [Config.AD_ADMIN_GROUP, Config.AD_SCHEDULING_ADMIN_GROUP]},
            'portal_admin': {'password': 'password', 'display_name': 'Portal Admin (Test)', 'groups': [Config.AD_PORTAL_ADMIN_GROUP]},
             'no_group_user': {'password': 'password', 'display_name': 'No Group User', 'groups': []}
        }

        if username in test_users and test_users[username]['password'] == password:
            user = test_users[username]
            is_portal_admin = Config.AD_PORTAL_ADMIN_GROUP in user['groups']
            is_admin = Config.AD_ADMIN_GROUP in user['groups'] or is_portal_admin
            is_user = Config.AD_USER_GROUP in user['groups'] or is_portal_admin
            is_scheduling_admin = Config.AD_SCHEDULING_ADMIN_GROUP in user['groups'] or is_portal_admin
            is_scheduling_user = Config.AD_SCHEDULING_USER_GROUP in user['groups'] or is_portal_admin

            if not any([is_admin, is_user, is_scheduling_admin, is_scheduling_user]):
                 return None

            return {
                'username': username, 'display_name': user['display_name'],
                'email': f'{username}@{Config.AD_DOMAIN or "test.local"}', 'groups': user['groups'],
                'is_admin': is_admin, 'is_user': is_user,
                'is_scheduling_admin': is_scheduling_admin, 'is_scheduling_user': is_scheduling_user,
                'is_portal_admin': is_portal_admin,
            }
        return None

    # Real AD Authentication
    if not Config.AD_SERVER or not Config.AD_DOMAIN:
        print("AD_SERVER or AD_DOMAIN not configured. Cannot perform AD authentication.")
        return None

    try:
        server = Server(Config.AD_SERVER, port=Config.AD_PORT, get_info=ALL)
        user_principal = f'{username}@{Config.AD_DOMAIN}'

        try:
            user_conn = Connection(server, user=user_principal, password=password, authentication=SIMPLE, auto_bind=True)
            # If bind succeeds, authentication is successful
            user_conn.unbind()
            print(f"AD authentication successful for user: {username}")

            # Now get user groups and info (critical step)
            user_info = get_user_groups(username)

            if user_info:
                is_portal_admin = Config.AD_PORTAL_ADMIN_GROUP in user_info['groups']
                # Determine base roles from AD groups
                is_in_admin = Config.AD_ADMIN_GROUP in user_info['groups'] or is_portal_admin
                is_in_user = Config.AD_USER_GROUP in user_info['groups'] or is_portal_admin
                is_in_scheduling_admin = Config.AD_SCHEDULING_ADMIN_GROUP in user_info['groups'] or is_portal_admin
                is_in_scheduling_user = Config.AD_SCHEDULING_USER_GROUP in user_info['groups'] or is_portal_admin

                # User must be in at least one relevant group OR be portal admin to log in
                if not any([is_in_admin, is_in_user, is_in_scheduling_admin, is_in_scheduling_user]):
                    print(f"User {username} authenticated but not in required base AD groups")
                    return None # No base role, cannot log in

                return {
                    'username': username,
                    'display_name': user_info['display_name'],
                    'email': user_info['email'],
                    'groups': user_info['groups'],
                    'is_admin': is_in_admin,
                    'is_user': is_in_user,
                    'is_scheduling_admin': is_in_scheduling_admin,
                    'is_scheduling_user': is_in_scheduling_user,
                    'is_portal_admin': is_portal_admin,
                }
            else:
                 # This case means authentication worked, but group lookup failed
                 print(f"AD authentication succeeded for {username}, but failed to retrieve group info. Denying login.")
                 return None

        except ldap3.core.exceptions.LDAPBindError:
            # This is the expected exception for wrong password
            print(f"Invalid AD credentials for user: {username}")
            return None # Failed AD auth

    except ldap3.core.exceptions.LDAPSocketOpenError as e:
         print(f"LDAP Connection Error authenticating {username}: Could not connect to AD server {Config.AD_SERVER}:{Config.AD_PORT}. Details: {e}")
         return None # Indicate connection failure
    except Exception as e:
        import traceback
        print(f"Unexpected AD Authentication error for {username}: {str(e)}")
        traceback.print_exc()
        return None

    return None # Fallback


# --- Helper to get specific permissions ---
def _get_specific_permissions(session):
    """ Fetches specific permissions from the DB for the logged-in user. """
    if 'user' in session and 'username' in session['user']:
        try:
            return permissions_db.get_user_permissions(session['user']['username'])
        except Exception as e:
            print(f"Error fetching specific permissions for {session['user']['username']}: {e}")
            return {
                'can_view_scheduling': False, 'can_edit_scheduling': False,
                'can_view_downtime': False, 'can_view_reports': False
            }
    return {}

# --- Updated Permission Check Functions ---

def require_login(session):
    return 'user' in session

def require_portal_admin(session):
    if 'user' in session:
        return (session['user'].get('username') == LOCAL_ADMIN_USERNAME or
                session['user'].get('is_portal_admin', False))
    return False

def require_admin(session):
    if 'user' in session:
        return (session['user'].get('username') == LOCAL_ADMIN_USERNAME or
                session['user'].get('is_portal_admin', False) or
                session['user'].get('is_admin', False)) # is_admin = Downtime Admin
    return False

def require_user(session):
    if 'user' in session:
        if (session['user'].get('username') == LOCAL_ADMIN_USERNAME or
            session['user'].get('is_portal_admin', False) or
            session['user'].get('is_admin', False) or
            session['user'].get('is_user', False)):
            return True
        specific_perms = _get_specific_permissions(session)
        return specific_perms.get('can_view_downtime', False)
    return False

def require_scheduling_admin(session):
    if 'user' in session:
        if (session['user'].get('username') == LOCAL_ADMIN_USERNAME or
            session['user'].get('is_portal_admin', False) or
            session['user'].get('is_scheduling_admin', False)):
            return True
        specific_perms = _get_specific_permissions(session)
        return specific_perms.get('can_edit_scheduling', False)
    return False

def require_scheduling_user(session):
    if 'user' in session:
        if (session['user'].get('username') == LOCAL_ADMIN_USERNAME or
            session['user'].get('is_portal_admin', False) or
            session['user'].get('is_scheduling_admin', False) or
            session['user'].get('is_scheduling_user', False)):
            return True
        specific_perms = _get_specific_permissions(session)
        return specific_perms.get('can_view_scheduling', False) or specific_perms.get('can_edit_scheduling', False)
    return False

def require_reports_user(session):
    if 'user' in session:
        if (session['user'].get('username') == LOCAL_ADMIN_USERNAME or
            session['user'].get('is_portal_admin', False) or
            session['user'].get('is_admin', False) or
            session['user'].get('is_scheduling_admin', False)):
            return True
        specific_perms = _get_specific_permissions(session)
        return specific_perms.get('can_view_reports', False)
    return False

def test_ad_connection():
    if Config.TEST_MODE:
        return True
    if not Config.AD_SERVER or not Config.AD_DOMAIN or not Config.AD_SERVICE_ACCOUNT or not Config.AD_SERVICE_PASSWORD:
        print("AD connection test skipped: Missing AD configuration in .env")
        return False
    try:
        server = Server(Config.AD_SERVER, port=Config.AD_PORT, get_info=ALL)
        service_user = f'{Config.AD_SERVICE_ACCOUNT}@{Config.AD_DOMAIN}'
        conn = Connection(server, user=service_user, password=Config.AD_SERVICE_PASSWORD, authentication=SIMPLE, auto_bind=True)
        conn.unbind()
        return True
    except ldap3.core.exceptions.LDAPSocketOpenError as e:
        print(f"AD connection test failed: Could not connect to AD server {Config.AD_SERVER}:{Config.AD_PORT}. Details: {e}")
        return False
    except ldap3.core.exceptions.LDAPBindError as e:
         print(f"AD connection test failed: Bind error using service account {service_user}. Check credentials. Details: {e}")
         return False
    except Exception as e:
        print(f"AD connection test failed with unexpected error: {str(e)}")
        return False