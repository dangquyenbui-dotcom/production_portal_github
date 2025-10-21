# auth/ad_auth.py
"""
Azure AD (OIDC) Authentication Module using MSAL Python
Handles user authentication and authorization via Azure AD.
Includes local fallback admin account.
REMOVED session cache saving to reduce cookie size.
ADDED detailed logging for local admin auth.
UPDATED local admin password hash.
FIXED email fallback logic.
"""

import msal
import uuid
from flask import session, url_for, request
from config import Config
from werkzeug.security import check_password_hash

# --- NEW Local Admin Configuration ---
LOCAL_ADMIN_USERNAME = 'PP_Local_Admin'
# Hash generated for password: (e]sB3)x81Y0 (Generated on 2025-10-21)
LOCAL_ADMIN_PASSWORD_HASH = 'pbkdf2:sha256:1000000$2e2sUY1RWO7hJ0fn$07324b3dc0894073efcf865d30ff1694965a77096db9a34e40e99dc1addabf01'

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
    session["state"] = state or str(uuid.uuid4())
    auth_url = _build_msal_app().get_authorization_request_url(
        scopes or Config.AAD_SCOPES,
        state=session["state"],
        redirect_uri=url_for("main.authorized", _external=True)
    )
    return auth_url

def _get_token_from_code(authority=None, scopes=None, request_args=None):
    """Handles the callback from Azure AD to exchange code for token."""
    if request_args.get("state") != session.get("state"):
        session.pop("state", None)
        raise ValueError("State mismatch error.")
    session.pop("state", None)

    if "error" in request_args:
        raise ValueError(f"Azure AD Error: {request_args.get('error')}, Description: {request_args.get('error_description')}")

    if request_args.get("code"):
        cca = _build_msal_app()
        result = cca.acquire_token_by_authorization_code(
            request_args["code"],
            scopes=scopes or Config.AAD_SCOPES,
            redirect_uri=url_for("main.authorized", _external=True)
        )

        if not result:
             raise ValueError("Failed to acquire token. Result was empty.")
        elif "error" in result:
             raise ValueError(f"Error acquiring token: {result.get('error_description', 'Unknown MSAL error')}")

        return result
    else:
        raise ValueError("Authorization code not found in callback.")


# --- Session Cache (Functions kept but not used during login token exchange) ---
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
    Returns TWO dictionaries: one for the session, one potentially richer for logging.
    """
    username = id_token_claims.get("preferred_username", id_token_claims.get("upn", "Unknown"))
    display_name = id_token_claims.get("name", username)

    # --- FIXED EMAIL FALLBACK LOGIC ---
    email_claim = id_token_claims.get("email")
    if email_claim:
        email = email_claim # Use email claim if present
    elif '@' in username:
        email = username # Use username if it looks like an email
    else:
        email = f"{username}@<domain_fallback>" # Construct fallback only if needed
    # --- END FIX ---

    user_groups = id_token_claims.get("groups", [])
    user_roles = id_token_claims.get("roles", [])

    # *** Permission Mapping Logic ***
    is_portal_admin = Config.AD_PORTAL_ADMIN_GROUP in user_groups or Config.AD_PORTAL_ADMIN_GROUP in user_roles
    is_admin = Config.AD_ADMIN_GROUP in user_groups or Config.AD_ADMIN_GROUP in user_roles or is_portal_admin
    is_user = Config.AD_USER_GROUP in user_groups or Config.AD_USER_GROUP in user_roles or is_portal_admin
    is_scheduling_admin = Config.AD_SCHEDULING_ADMIN_GROUP in user_groups or Config.AD_SCHEDULING_ADMIN_GROUP in user_roles or is_portal_admin
    is_scheduling_user = Config.AD_SCHEDULING_USER_GROUP in user_groups or Config.AD_SCHEDULING_USER_GROUP in user_roles or is_portal_admin

    has_permission = any([is_admin, is_user, is_scheduling_admin, is_scheduling_user, is_portal_admin])
    if not has_permission:
        print(f"[DEBUG] User {username} authenticated but not in required Azure AD groups/roles (Object IDs or App Roles)")
        return None, None

    # --- Dictionary for Flask Session (Minimal Data) ---
    session_user_info = {
        'username': username.split('@')[0] if '@' in username else username,
        'display_name': display_name,
        'email': email, # Use the correctly determined email
        'is_admin': is_admin,
        'is_user': is_user,
        'is_scheduling_admin': is_scheduling_admin,
        'is_scheduling_user': is_scheduling_user,
        'is_portal_admin': is_portal_admin,
    }

    # --- Dictionary for Logging ---
    log_user_info = {
         'username': session_user_info['username'],
         'display_name': display_name,
         'email': email, # Use the correctly determined email
         'groups': user_groups,
         'roles': user_roles,
         'is_admin': is_admin,
         'is_user': is_user,
         'is_scheduling_admin': is_scheduling_admin,
         'is_scheduling_user': is_scheduling_user,
         'is_portal_admin': is_portal_admin,
    }

    return session_user_info, log_user_info


# --- Local Admin Fallback Authentication ---
def authenticate_local_admin(username, password):
    """Authenticate local admin credentials only."""
    # *** ADDED DETAILED LOGGING ***
    print(f"\n[DEBUG] Attempting local admin authentication...")
    print(f"[DEBUG]   Username entered: '{username}'")
    # Mask password in log for security
    print(f"[DEBUG]   Password entered: {'*' * len(password)}")
    print(f"[DEBUG]   Expected Username: '{LOCAL_ADMIN_USERNAME}'")
    print(f"[DEBUG]   Stored Hash: '{LOCAL_ADMIN_PASSWORD_HASH[:15]}...'")

    username_match = (username == LOCAL_ADMIN_USERNAME)
    print(f"[DEBUG]   Username matches config: {username_match}")

    if not username_match:
        print(f"[DEBUG]   Authentication failed: Username mismatch.")
        return None, None

    try:
        password_match = check_password_hash(LOCAL_ADMIN_PASSWORD_HASH, password)
        print(f"[DEBUG]   Password hash check result: {password_match}")
    except Exception as e:
        print(f"[DEBUG]   Error during password hash check: {e}")
        password_match = False

    if username_match and password_match:
        print(f"[DEBUG]   Authentication successful for local admin: {username}")
        # *** END ADDED LOGGING ***
        session_info = {
            'username': LOCAL_ADMIN_USERNAME,
            'display_name': 'Local Portal Admin',
            'email': 'local_admin@system.local',
            'is_admin': True,
            'is_user': True,
            'is_scheduling_admin': True,
            'is_scheduling_user': True,
            'is_portal_admin': True,
        }
        log_info = session_info.copy()
        log_info['groups'] = ['LocalAdmin']
        log_info['roles'] = []
        return session_info, log_info
    else:
        # *** ADDED LOGGING ***
        print(f"[DEBUG]   Authentication failed: Password mismatch.")
        # *** END ADDED LOGGING ***
        return None, None

# --- Permission Check Functions ---
def require_login(session):
    return 'user' in session

def require_admin(session):
    user = session.get('user')
    return user and (user.get('is_admin') or user.get('is_portal_admin') or user.get('username') == LOCAL_ADMIN_USERNAME)

def require_user(session):
    user = session.get('user')
    return user and (user.get('is_user') or user.get('is_admin') or user.get('is_scheduling_admin') or user.get('is_scheduling_user') or user.get('is_portal_admin') or user.get('username') == LOCAL_ADMIN_USERNAME)

def require_scheduling_admin(session):
    user = session.get('user')
    return user and (user.get('is_scheduling_admin') or user.get('is_portal_admin') or user.get('username') == LOCAL_ADMIN_USERNAME)

def require_scheduling_user(session):
    user = session.get('user')
    return user and (user.get('is_scheduling_user') or user.get('is_scheduling_admin') or user.get('is_portal_admin') or user.get('username') == LOCAL_ADMIN_USERNAME)