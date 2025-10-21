# routes/main.py
"""
Main routes for Production Portal
*** MODIFIED FOR AZURE AD AUTHENTICATION ***
*** ADDED TEMPORARY CLAIM PRINTING ***
"""
import os
from flask import Blueprint, render_template, redirect, url_for, session, request, flash, jsonify
from functools import wraps
# *** ADDED json FOR PRINTING ***
import json

# --- MODIFIED: Import MSAL helpers and potentially local admin auth ---
from auth.ad_auth import (
    _build_auth_url,
    _get_token_from_code,
    build_user_session,
    authenticate_local_admin, # Keep if using local admin fallback
    require_login,
    # require_admin (no longer needed directly here, used in templates/other routes)
    # *** ADDED LOCAL_ADMIN_USERNAME FOR CHECK ***
    LOCAL_ADMIN_USERNAME
)
from config import Config

# Import database modules (Session validation still uses local DB)
from database import facilities_db, lines_db, categories_db, downtimes_db, sessions_db, users_db
# from database.connection import DatabaseConnection # No direct need here now

# Import i18n
from i18n_config import I18nConfig, _

main_bp = Blueprint('main', __name__)

# --- Session Validation (remains mostly the same, uses local DB) ---
def validate_session(f):
    """Decorator to validate session on each request"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' in session and 'session_id' in session:
            # Validate the session is still active in the LOCAL DB
            if not sessions_db.validate_session(session['session_id'], session['user']['username']):
                # Clear local session if DB session is invalid
                session.clear()
                flash(_('Your session has expired or you logged in from another location'), 'error')
                # Redirect to initiate Azure AD login again
                return redirect(url_for('main.login'))
        elif 'user' not in session and request.endpoint not in ['main.login', 'main.authorized', 'main.logout', 'static']:
             # If not logged in and accessing a protected page, redirect to login
             return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function

@main_bp.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('main.dashboard'))
    # If not logged in, redirect to Azure AD login flow
    return redirect(url_for('main.login'))

@main_bp.route('/switch-language/<language>')
def switch_language(language):
    # ... (language switching logic remains the same) ...
    if I18nConfig.switch_language(language):
        flash(_('Language changed successfully'), 'success')
    else:
        flash(_('Invalid language selection'), 'error')
    referrer = request.referrer
    return redirect(referrer or url_for('main.dashboard'))


# --- MODIFIED: Login Route - Initiates Azure AD Flow OR handles local admin ---
@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    # If user is already logged in, redirect to dashboard
    if 'user' in session:
        return redirect(url_for('main.dashboard'))

    # If POST, it's potentially the local admin fallback login
    if request.method == 'POST':
        # --- Local Admin Fallback Logic (Optional) ---
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if username == LOCAL_ADMIN_USERNAME: # Use constant from ad_auth
            user_info = authenticate_local_admin(username, password)
            if user_info:
                # Local admin authenticated, handle session like before
                new_session_id = sessions_db.generate_session_id()
                from utils import get_client_info
                ip, user_agent = get_client_info()
                sessions_db.create_session(new_session_id, username, ip, user_agent)
                session.permanent = True
                session['user'] = user_info
                session['session_id'] = new_session_id
                print(f"🔑 Local admin {username} logged in successfully.")
                try: # Log local admin login
                    users_db.log_login(username=username, display_name=user_info.get('display_name'), email=user_info.get('email'), groups=user_info.get('groups', []), is_admin=True, ip=ip, user_agent=user_agent)
                except Exception as e: print(f"Failed to log local admin login: {e}")
                return redirect(url_for('main.dashboard'))
            else:
                flash(_('Invalid credentials or access denied'), 'error')
                return render_template('login.html', config=Config) # Show login page again
        else:
             # Regular user trying to POST - redirect to Azure AD flow
             return redirect(_build_auth_url())
    else:
        # If GET request, initiate Azure AD login flow
        # Clear any potential stale session data before redirecting
        session.clear()
        # Generate Azure AD login URL and redirect the user
        auth_url = _build_auth_url()
        return redirect(auth_url)

# --- NEW: Callback Route to handle Azure AD response ---
@main_bp.route('/get_token') # Matches the redirect URI configured in Azure
def authorized():
    try:
        # Exchange the authorization code for tokens
        result = _get_token_from_code(request_args=request.args)

        if "error" in result:
             # Handle errors from token acquisition
             print(f"Error acquiring token: {result.get('error_description')}")
             flash(f"Login failed: {result.get('error_description', 'Unknown Azure AD error')}", 'error')
             return redirect(url_for('main.index')) # Redirect to home/login start

        # Check if ID token is present
        if "id_token_claims" not in result:
            print("Error: 'id_token_claims' not found in token response.")
            flash("Login failed: Could not retrieve user identity information.", 'error')
            return redirect(url_for('main.index'))

        # Extract user info and map permissions
        user_claims = result["id_token_claims"]

        # *** TEMPORARY DEBUG PRINT ***
        print("---- AZURE AD CLAIMS ----")
        print(json.dumps(user_claims, indent=2))
        print("-------------------------")
        # *** END TEMPORARY DEBUG PRINT ***

        user_info = build_user_session(user_claims)

        if user_info is None:
            # User authenticated but doesn't have necessary permissions/groups
            flash(_('You do not have permission to access this application.'), 'error')
            # Log this attempt maybe?
            # print(f"Permission denied for user: {user_claims.get('preferred_username')}") # This is already printed in build_user_session
            return redirect(url_for('main.login')) # Send back to login start

        # --- Login successful - Set up local session ---
        username = user_info['username'] # Use the extracted username (without domain)
        new_session_id = sessions_db.generate_session_id()
        from utils import get_client_info
        ip, user_agent = get_client_info()

        # Create session in LOCAL database (for single-session enforcement)
        sessions_db.create_session(new_session_id, username, ip, user_agent)

        # Set Flask session
        session.permanent = True
        session['user'] = user_info
        # Store the raw ID token claims if needed for other purposes (like API calls)
        # session['claims'] = user_claims
        session['session_id'] = new_session_id # Store local session ID

        print(f"✅ User {username} logged in successfully via Azure AD.")

        # Log the login event to LOCAL DB
        try:
            users_db.log_login(
                username=username,
                display_name=user_info.get('display_name'),
                email=user_info.get('email'),
                groups=user_info.get('groups', []), # Store Azure groups/roles
                is_admin=user_info.get('is_admin', False), # Based on mapping
                ip=ip,
                user_agent=user_agent
            )
        except Exception as e:
            print(f"Failed to log Azure AD login event: {str(e)}")

        # Redirect to the dashboard
        return redirect(url_for('main.dashboard'))

    except ValueError as e:
         # Handle state mismatch or code errors
         print(f"Authentication callback error: {e}")
         flash(f"Login failed: {e}", 'error')
         return redirect(url_for('main.login'))
    except Exception as e:
         # Catch unexpected errors
         print(f"Unexpected error during Azure AD callback: {e}")
         import traceback
         traceback.print_exc()
         flash("An unexpected error occurred during login.", 'error')
         return redirect(url_for('main.login'))


# --- Dashboard Route (remains mostly the same, uses @validate_session) ---
@main_bp.route('/dashboard')
@validate_session # Ensures user is logged in via Flask session
def dashboard():
    # require_login check might be redundant due to @validate_session
    # if not require_login(session): return redirect(url_for('main.login'))

    # Get stats (remains the same)
    stats = { 'facilities': 0, 'production_lines': 0, 'recent_downtime_count': 0, 'categories': 0 }
    try:
        stats['facilities'] = len(facilities_db.get_all(active_only=True) or [])
        stats['production_lines'] = len(lines_db.get_all(active_only=True) or [])
        stats['categories'] = len(categories_db.get_all(active_only=True) or [])
        stats['recent_downtime_count'] = len(downtimes_db.get_recent(days=7) or [])
    except Exception as e: print(f"Error getting dashboard stats: {e}")

    return render_template('dashboard.html', user=session['user'], stats=stats, config=Config)


# --- MODIFIED: Logout Route - Clears local session and redirects to Azure AD logout ---
@main_bp.route('/logout')
def logout():
    username = session.get('user', {}).get('username', 'Unknown')
    session_id = session.get('session_id')

    # End the session in the LOCAL database
    if session_id:
        sessions_db.end_session(session_id)

    # Clear Flask session keys specific to your app
    session.pop('user', None)
    session.pop('session_id', None)
    session.pop('token_cache', None) # Clear MSAL cache if stored in session
    session.pop('state', None)

    print(f"User {username} logged out locally.")
    flash(_('You have been successfully logged out'), 'info')

    # Redirect to Azure AD logout endpoint for Single Sign-Out (SSO)
    # This logs the user out of Azure AD itself
    logout_uri = url_for('main.index', _external=True) # Where Azure AD redirects back after logout
    azure_logout_url = (
        f"{Config.AAD_AUTHORITY}/oauth2/v2.0/logout"
        f"?post_logout_redirect_uri={logout_uri}"
    )
    return redirect(azure_logout_url)


# --- Status Route (remains mostly the same, AD check removed) ---
@main_bp.route('/status')
@validate_session
def status():
    # if not require_login(session): return redirect(url_for('main.login'))
    # Use the specific permission check now
    from auth.ad_auth import require_admin as require_auth_admin # Avoid name clash
    if not require_auth_admin(session): # Use imported check
        flash(_('Admin privileges required'), 'error')
        return redirect(url_for('main.dashboard'))

    status_info = {
        # 'ad_connected': True, # No direct AD connection to test now
        'db_connected': False,
        'test_mode': Config.TEST_MODE,
        'auth_mode': 'Azure AD (OIDC)',
        'facilities_count': 0,
        'lines_count': 0,
        'users_today': 0, # Consider fetching this if needed
        'active_sessions': 0 # From local sessions DB
    }
    try: # Test DB connection
        db_conn = sessions_db.db # Get the underlying connection object
        status_info['db_connected'] = db_conn.test_connection()
        if status_info['db_connected']:
             # Get counts, active sessions etc. (same as before)
             status_info['active_sessions'] = sessions_db.get_active_sessions_count()
             # ... fetch other counts ...
             # Example: Fetch facility count if needed
             status_info['facilities_count'] = len(facilities_db.get_all(active_only=True) or [])
             status_info['lines_count'] = len(lines_db.get_all(active_only=True) or [])
    except Exception as e: print(f"Error in status check: {e}")

    # Render status (template needs updating to remove AD specific parts)
    return render_template('status.html', user=session['user'], status=status_info, config=Config)