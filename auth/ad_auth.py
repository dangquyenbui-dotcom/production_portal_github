# auth/ad_auth.py
"""
Azure AD (OIDC) Authentication Module using MSAL Python
Handles user authentication and authorization via Azure AD.
"""

import msal
import uuid
from flask import session, url_for, request
from config import Config
from werkzeug.security import check_password_hash # Keep for local admin fallback

# --- Local Admin Configuration (remains the same) ---
LOCAL_ADMIN_USERNAME = 'production_portal_admin'
LOCAL_ADMIN_PASSWORD_HASH = 'pbkdf2:sha256:1000000$7GUCiDMbjttS4Sa9$87463836cef236308961cbf57d01a4cd1b14e79c7bbd707ff15faa6a947c1609'

# --- MSAL Setup ---
def _build_msal_app(cache=None):
    """Builds the MSAL Confidential Client Application instance."""
    return msal.ConfidentialClientApplication(
        Config.AAD_CLIENT_ID,
        authority=Config.AAD_AUTHORITY,
        client_credential=Config.AAD_CLIENT_SECRET,
        token_cache=cache
    )

def _build_auth_url(authority=None, scopes=None, state=None):
    """Generates the Azure AD authorization URL."""
    # Ensure session state for CSRF protection
    session["state"] = state or str(uuid.uuid4())
    # Generate the URL to redirect the user to Azure AD login
    auth_url = _build_msal_app().get_authorization_request_url(
        scopes or Config.AAD_SCOPES,
        state=session["state"],
        redirect_uri=url_for("main.authorized", _external=True) # Needs callback route named 'authorized' in main_bp
    )
    return auth_url

def _get_token_from_code(authority=None, scopes=None, request_args=None):
    """Handles the callback from Azure AD to exchange code for token."""
    # Check for state mismatch (CSRF protection)
    if request_args.get("state") != session.get("state"):
        raise ValueError("State mismatch error.")
    # Check for authentication errors from Azure AD
    if "error" in request_args:
        raise ValueError(f"Azure AD Error: {request_args.get('error')}, Description: {request_args.get('error_description')}")

    if request_args.get("code"):
        cache = _load_cache()
        cca = _build_msal_app(cache=cache)
        # Exchange the authorization code for an ID token and access token
        result = cca.acquire_token_by_authorization_code(
            request_args["code"],
            scopes=scopes or Config.AAD_SCOPES,
            redirect_uri=url_for("main.authorized", _external=True)
        )
        _save_cache(cache)
        return result
    else:
        raise ValueError("Authorization code not found in callback.")


# --- Session Cache (Optional but recommended for token management) ---
def _load_cache():
    cache = msal.SerializableTokenCache()
    if session.get("token_cache"):
        cache.deserialize(session["token_cache"])
    return cache

def _save_cache(cache):
    if cache.has_state_changed:
        session["token_cache"] = cache.serialize()


# --- Map User Info and Permissions ---
def build_user_session(id_token_claims):
    """
    Extracts user info from the ID token claims and determines permissions.
    """
    username = id_token_claims.get("preferred_username", id_token_claims.get("upn", "Unknown"))
    display_name = id_token_claims.get("name", username)
    email = id_token_claims.get("email", f"{username}@<domain_fallback>") # Add fallback domain if email missing
    # Important: 'groups' claim might contain Object IDs or names depending on Azure config
    # 'roles' claim is used if you configured App Roles in the registration
    user_groups = id_token_claims.get("groups", [])
    user_roles = id_token_claims.get("roles", [])

    # *** PERMISSION MAPPING LOGIC ***
    # Adjust this based on whether you use Azure AD group names, Object IDs, or App Roles
    # This example assumes you're matching against the group *names* defined in Config
    is_portal_admin = Config.AD_PORTAL_ADMIN_GROUP in user_groups or Config.AD_PORTAL_ADMIN_GROUP in user_roles
    is_admin = Config.AD_ADMIN_GROUP in user_groups or Config.AD_ADMIN_GROUP in user_roles or is_portal_admin
    is_user = Config.AD_USER_GROUP in user_groups or Config.AD_USER_GROUP in user_roles or is_portal_admin
    is_scheduling_admin = Config.AD_SCHEDULING_ADMIN_GROUP in user_groups or Config.AD_SCHEDULING_ADMIN_GROUP in user_roles or is_portal_admin
    is_scheduling_user = Config.AD_SCHEDULING_USER_GROUP in user_groups or Config.AD_SCHEDULING_USER_GROUP in user_roles or is_portal_admin

    # Check if user has at least one relevant permission
    if not any([is_admin, is_user, is_scheduling_admin, is_scheduling_user]):
        print(f"User {username} authenticated but not in required Azure AD groups/roles")
        # You might want to flash a message here or handle it in the callback route
        return None # Indicate insufficient permissions

    user_info = {
        'username': username.split('@')[0] if '@' in username else username, # Get just the account name part
        'display_name': display_name,
        'email': email,
        'groups': user_groups, # Store the actual Azure groups/roles
        'roles': user_roles,
        'is_admin': is_admin,
        'is_user': is_user,
        'is_scheduling_admin': is_scheduling_admin,
        'is_scheduling_user': is_scheduling_user,
        'is_portal_admin': is_portal_admin,
        # Store claims for potential future use (e.g., calling APIs)
        # 'claims': id_token_claims
    }
    return user_info


# --- Local Admin Fallback Authentication ---
def authenticate_local_admin(username, password):
    """Authenticate local admin credentials only."""
    if username == LOCAL_ADMIN_USERNAME and check_password_hash(LOCAL_ADMIN_PASSWORD_HASH, password):
        print(f"Authenticated local admin: {username}")
        # Grant all admin permissions
        return {
            'username': LOCAL_ADMIN_USERNAME,
            'display_name': 'Local Portal Admin',
            'email': 'local_admin@system.local',
            'groups': ['LocalAdmin'],
            'roles': ['LocalAdminRole'],
            'is_admin': True,
            'is_user': True,
            'is_scheduling_admin': True,
            'is_scheduling_user': True,
            'is_portal_admin': True,
        }
    return None

# --- Permission Check Functions (Leverage session data set by build_user_session) ---
def require_login(session):
    """Check if user is logged in (basic session check)."""
    return 'user' in session

def require_admin(session):
    """Check if user has Downtime Admin or Portal Admin rights."""
    user = session.get('user')
    return user and (user.get('is_admin') or user.get('is_portal_admin'))

def require_user(session):
    """Check if user has basic Downtime User rights (or higher)."""
    user = session.get('user')
    return user and (user.get('is_user') or user.get('is_admin') or user.get('is_portal_admin'))

def require_scheduling_admin(session):
    """Check if user has Scheduling Admin or Portal Admin rights."""
    user = session.get('user')
    return user and (user.get('is_scheduling_admin') or user.get('is_portal_admin'))

def require_scheduling_user(session):
    """Check if user has Scheduling User rights (or higher)."""
    user = session.get('user')
    return user and (user.get('is_scheduling_user') or user.get('is_scheduling_admin') or user.get('is_portal_admin'))

# AD Connection test is no longer relevant with OIDC/Azure AD
# def test_ad_connection():
#     return True # Or remove entirely