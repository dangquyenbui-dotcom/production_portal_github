# routes/main.py
"""
Main routes for Production Portal
*** MODIFIED FOR AZURE AD AUTHENTICATION & SESSION SIZE FIX ***
*** MODIFIED GET /login TO RENDER TEMPLATE ***
*** ADDED /login/microsoft ROUTE FOR AZURE AD REDIRECT ***
"""
import os
from flask import Blueprint, render_template, redirect, url_for, session, request, flash, jsonify
from functools import wraps
import json

# --- MODIFIED: Import MSAL helpers and potentially local admin auth ---
from auth.ad_auth import (
    _build_auth_url,
    _get_token_from_code,
    build_user_session,
    authenticate_local_admin, # Keep if using local admin fallback
    require_login,
    LOCAL_ADMIN_USERNAME
)
from config import Config

# Import database modules
from database import facilities_db, lines_db, categories_db, downtimes_db, sessions_db, users_db
from i18n_config import I18nConfig, _

main_bp = Blueprint('main', __name__)

# --- Session Validation ---
def validate_session(f):
    """Decorator to validate session on each request"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Allow access to login routes without validation
        if request.endpoint in ['main.login', 'main.login_microsoft', 'main.authorized', 'main.logout', 'static']:
             return f(*args, **kwargs)

        if 'user' in session and 'session_id' in session:
            # Validate the session is still active in the LOCAL DB
            if not sessions_db.validate_session(session['session_id'], session['user']['username']):
                session.clear()
                flash(_('Your session has expired or you logged in from another location'), 'error')
                return redirect(url_for('main.login')) # Redirect to login page
        elif 'user' not in session:
             # If not logged in and accessing a protected page, redirect to login
             return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function

@main_bp.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('main.dashboard'))
    # If not logged in, show the login page
    return redirect(url_for('main.login'))

@main_bp.route('/switch-language/<language>')
def switch_language(language):
    if I18nConfig.switch_language(language):
        flash(_('Language changed successfully'), 'success')
    else:
        flash(_('Invalid language selection'), 'error')
    referrer = request.referrer
    return redirect(referrer or url_for('main.dashboard'))


# --- MODIFIED: Login Route ---
@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('main.dashboard'))

    # POST handles local admin login submission
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        # Check only for the specific local admin username here
        if username == LOCAL_ADMIN_USERNAME:
            session_user_info, log_user_info = authenticate_local_admin(username, password)
            if session_user_info:
                # Local admin authenticated successfully
                new_session_id = sessions_db.generate_session_id()
                from utils import get_client_info
                ip, user_agent = get_client_info()
                sessions_db.create_session(new_session_id, username, ip, user_agent)
                session.permanent = True
                session['user'] = session_user_info
                session['session_id'] = new_session_id
                print(f"🔑 Local admin {username} logged in successfully.")
                try: # Log local admin login
                    users_db.log_login(
                        username=log_user_info['username'],
                        display_name=log_user_info.get('display_name'),
                        email=log_user_info.get('email'),
                        groups=log_user_info.get('groups', []),
                        is_admin=log_user_info.get('is_admin', False),
                        ip=ip,
                        user_agent=user_agent
                    )
                except Exception as e: print(f"Failed to log local admin login: {e}")
                return redirect(url_for('main.dashboard'))
            else:
                # Local admin credentials failed
                flash(_('Invalid credentials or access denied'), 'error')
                # Show login page again
                return render_template('login.html', config=Config)
        else:
            # If POST is not for local admin, treat as invalid attempt
            flash(_('Invalid credentials or access denied'), 'error')
            return render_template('login.html', config=Config)
    else:
        # --- MODIFICATION: GET request now RENDERS the login template ---
        # It no longer automatically redirects to Microsoft
        return render_template('login.html', config=Config)

# --- NEW ROUTE: To explicitly trigger Microsoft Login ---
@main_bp.route('/login/microsoft')
def login_microsoft():
    # Clear session before redirecting to avoid conflicts
    session.clear()
    # Build the Azure AD authorization URL and redirect
    auth_url = _build_auth_url()
    return redirect(auth_url)


# --- Callback Route (No changes needed here) ---
@main_bp.route('/get_token')
def authorized():
    try:
        result = _get_token_from_code(request_args=request.args)

        if not result or "error" in result:
             error_desc = result.get('error_description', 'Unknown Azure AD error') if result else 'Token acquisition failed'
             print(f"Error acquiring token: {error_desc}")
             flash(f"Login failed: {error_desc}", 'error')
             return redirect(url_for('main.login'))

        if "id_token_claims" not in result:
            print("Error: 'id_token_claims' not found in token response.")
            flash("Login failed: Could not retrieve user identity information.", 'error')
            return redirect(url_for('main.login'))

        user_claims = result["id_token_claims"]

        # *** TEMPORARY DEBUG PRINT - Can be removed later ***
        # print("---- AZURE AD CLAIMS ----")
        # print(json.dumps(user_claims, indent=2))
        # print("-------------------------")
        # *** END TEMPORARY DEBUG PRINT ***

        session_user_info, log_user_info = build_user_session(user_claims)

        if session_user_info is None:
            flash(_('You do not have permission to access this application.'), 'error')
            return redirect(url_for('main.login'))

        # --- Login successful - Set up local session ---
        username = session_user_info['username']
        new_session_id = sessions_db.generate_session_id()
        from utils import get_client_info
        ip, user_agent = get_client_info()

        sessions_db.create_session(new_session_id, username, ip, user_agent)

        session.permanent = True
        session['user'] = session_user_info
        session['session_id'] = new_session_id

        print(f"✅ User {username} logged in successfully via Azure AD.")

        # Log the login event
        try:
            users_db.log_login(
                username=log_user_info['username'],
                display_name=log_user_info.get('display_name'),
                email=log_user_info.get('email'),
                groups=log_user_info.get('groups', []),
                is_admin=log_user_info.get('is_admin', False),
                ip=ip,
                user_agent=user_agent
            )
        except Exception as e:
            print(f"Failed to log Azure AD login event: {str(e)}")

        return redirect(url_for('main.dashboard'))

    except ValueError as e:
         print(f"Authentication callback error: {e}")
         flash(f"Login failed: {e}", 'error')
         return redirect(url_for('main.login'))
    except Exception as e:
         print(f"Unexpected error during Azure AD callback: {e}")
         import traceback
         traceback.print_exc()
         flash("An unexpected error occurred during login.", 'error')
         return redirect(url_for('main.login'))


# --- Dashboard Route ---
@main_bp.route('/dashboard')
@validate_session
def dashboard():
    stats = { 'facilities': 0, 'production_lines': 0, 'recent_downtime_count': 0, 'categories': 0 }
    try:
        stats['facilities'] = len(facilities_db.get_all(active_only=True) or [])
        stats['production_lines'] = len(lines_db.get_all(active_only=True) or [])
        stats['categories'] = len(categories_db.get_all(active_only=True) or [])
        stats['recent_downtime_count'] = len(downtimes_db.get_recent(days=7) or [])
    except Exception as e: print(f"Error getting dashboard stats: {e}")

    return render_template('dashboard.html', user=session.get('user'), stats=stats, config=Config)


# --- Logout Route (No changes needed here) ---
@main_bp.route('/logout')
def logout():
    username = session.get('user', {}).get('username', 'Unknown')
    session_id = session.get('session_id')

    if session_id:
        sessions_db.end_session(session_id)

    # Clear Flask session keys
    session.pop('user', None)
    session.pop('session_id', None)
    session.pop('token_cache', None)
    session.pop('state', None)

    print(f"User {username} logged out locally.")
    flash(_('You have been successfully logged out'), 'info')

    logout_uri = url_for('main.index', _external=True)
    azure_logout_url = (
        f"{Config.AAD_AUTHORITY}/oauth2/v2.0/logout"
        f"?post_logout_redirect_uri={logout_uri}"
    )
    return redirect(azure_logout_url)


# --- Status Route (No changes needed here) ---
@main_bp.route('/status')
@validate_session
def status():
    from auth.ad_auth import require_admin as require_auth_admin
    if not require_auth_admin(session):
        flash(_('Admin privileges required'), 'error')
        return redirect(url_for('main.dashboard'))

    status_info = {
        'db_connected': False,
        'test_mode': Config.TEST_MODE,
        'auth_mode': 'Azure AD (OIDC)',
        'facilities_count': 0,
        'lines_count': 0,
        'users_today': 0,
        'active_sessions': 0
    }
    try:
        db_conn = sessions_db.db
        status_info['db_connected'] = db_conn.test_connection()
        if status_info['db_connected']:
             status_info['active_sessions'] = sessions_db.get_active_sessions_count()
             status_info['facilities_count'] = len(facilities_db.get_all(active_only=True) or [])
             status_info['lines_count'] = len(lines_db.get_all(active_only=True) or [])
             # stats = users_db.get_login_statistics()
             # status_info['users_today'] = stats.get('active_today', 0)
    except Exception as e: print(f"Error in status check: {e}")

    return render_template('status.html', user=session.get('user'), status=status_info, config=Config)