# routes/main.py
"""
Main routes for Production Portal
*** ADDED DEBUG PRINT STATEMENTS FOR EDGE HANG ISSUE ***
"""
import os
from flask import Blueprint, render_template, redirect, url_for, session, request, flash, jsonify, current_app
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
# Import the validate_session decorator defined in app.py (or wherever it resides now)
# Assuming it's passed via app context or imported if defined elsewhere
# If validate_session is defined in this file, ensure it uses sessions_db correctly.
# If it's defined in app.py, this import might not be needed if applied globally,
# but routes still need Flask components.
# from app import validate_session # Adjust if validate_session is in app.py

main_bp = Blueprint('main', __name__)

# --- Re-add validate_session decorator if it wasn't applied globally ---
# --- If it IS applied globally in app.py, you can remove the @validate_session lines ---
# --- For now, assume it's needed per-route as before ---
from app import validate_session # Assuming validate_session is now in app.py


@main_bp.route('/')
def index():
    # <<< DEBUGGING >>>
    print(f"--- Request received for / from {request.remote_addr} ---")
    print(f"Headers: {request.headers}")
    # <<< END DEBUGGING >>>
    if 'user' in session:
        print("--- User found in session, redirecting to dashboard ---")
        return redirect(url_for('main.dashboard'))
    # If not logged in, show the login page
    print("--- No user in session, redirecting to login ---")
    return redirect(url_for('main.login'))

@main_bp.route('/switch-language/<language>')
def switch_language(language):
    # <<< DEBUGGING >>>
    print(f"--- Request received for /switch-language/{language} from {request.remote_addr} ---")
    # <<< END DEBUGGING >>>
    if I18nConfig.switch_language(language):
        flash(_('Language changed successfully'), 'success')
    else:
        flash(_('Invalid language selection'), 'error')
    referrer = request.referrer
    return redirect(referrer or url_for('main.dashboard'))


# --- MODIFIED: Login Route ---
@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    # <<< DEBUGGING >>>
    print(f"--- Request received for /login [{request.method}] from {request.remote_addr} ---")
    # <<< END DEBUGGING >>>
    if 'user' in session:
        print("--- User found in session, redirecting to dashboard from /login ---")
        return redirect(url_for('main.dashboard'))

    # POST handles local admin login submission
    if request.method == 'POST':
        # <<< DEBUGGING >>>
        print("--- Handling POST request for /login (Local Admin attempt) ---")
        # <<< END DEBUGGING >>>
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        # Check only for the specific local admin username here
        if username == LOCAL_ADMIN_USERNAME:
            session_user_info, log_user_info = authenticate_local_admin(username, password)
            if session_user_info:
                # Local admin authenticated successfully
                new_session_id = sessions_db.generate_session_id()
                from utils import get_client_info # Keep import local if only used here
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
                print("--- Redirecting to dashboard after local admin login ---")
                return redirect(url_for('main.dashboard'))
            else:
                # Local admin credentials failed
                flash(_('Invalid credentials or access denied'), 'error')
                # Show login page again
                print("--- Rendering login template after failed local admin attempt ---")
                return render_template('login.html', config=Config)
        else:
            # If POST is not for local admin, treat as invalid attempt
            flash(_('Invalid credentials or access denied'), 'error')
            print("--- Rendering login template after invalid POST username ---")
            return render_template('login.html', config=Config)
    else:
        # --- GET request renders the login template ---
        # <<< DEBUGGING >>>
        print("--- Rendering login template for GET request ---")
        # <<< END DEBUGGING >>>
        return render_template('login.html', config=Config)

# --- NEW ROUTE: To explicitly trigger Microsoft Login ---
@main_bp.route('/login/microsoft')
def login_microsoft():
    # <<< DEBUGGING >>>
    print(f"--- Request received for /login/microsoft from {request.remote_addr} ---")
    # <<< END DEBUGGING >>>
    # Clear session before redirecting to avoid conflicts
    session.clear()
    # Build the Azure AD authorization URL and redirect
    print("--- Building Azure AD auth URL and redirecting ---")
    auth_url = _build_auth_url()
    return redirect(auth_url)


# --- Callback Route (No changes needed here, but adding logging) ---
@main_bp.route('/get_token')
def authorized():
    # <<< DEBUGGING >>>
    print(f"--- Request received for /get_token (Azure AD Callback) from {request.remote_addr} ---")
    print(f"Callback Args: {request.args}")
    # <<< END DEBUGGING >>>
    try:
        # <<< DEBUGGING >>>
        print("--- Attempting to get token from code ---")
        # <<< END DEBUGGING >>>
        result = _get_token_from_code(request_args=request.args)
        # <<< DEBUGGING >>>
        print(f"--- Token acquisition result obtained (contains keys: {'error' in result if result else 'N/A'}) ---")
        # <<< END DEBUGGING >>>

        if not result or "error" in result:
             error_desc = result.get('error_description', 'Unknown Azure AD error') if result else 'Token acquisition failed'
             print(f"Error acquiring token: {error_desc}")
             flash(f"Login failed: {error_desc}", 'error')
             print("--- Redirecting to login due to token error ---")
             return redirect(url_for('main.login'))

        if "id_token_claims" not in result:
            print("Error: 'id_token_claims' not found in token response.")
            flash("Login failed: Could not retrieve user identity information.", 'error')
            print("--- Redirecting to login due to missing claims ---")
            return redirect(url_for('main.login'))

        user_claims = result["id_token_claims"]
        # <<< DEBUGGING >>>
        print("--- Successfully obtained ID token claims ---")
        # print(json.dumps(user_claims, indent=2)) # Optional: Uncomment for full claims details
        # <<< END DEBUGGING >>>

        session_user_info, log_user_info = build_user_session(user_claims)

        if session_user_info is None:
            flash(_('You do not have permission to access this application.'), 'error')
            print("--- Redirecting to login due to lack of permissions (build_user_session returned None) ---")
            return redirect(url_for('main.login'))

        # --- Login successful - Set up local session ---
        username = session_user_info['username']
        new_session_id = sessions_db.generate_session_id()
        from utils import get_client_info # Keep import local
        ip, user_agent = get_client_info()

        # <<< DEBUGGING >>>
        print(f"--- Creating local session for user: {username} ---")
        # <<< END DEBUGGING >>>
        sessions_db.create_session(new_session_id, username, ip, user_agent)

        session.permanent = True
        session['user'] = session_user_info
        session['session_id'] = new_session_id

        print(f"✅ User {username} logged in successfully via Azure AD.")

        # Log the login event
        try:
            # <<< DEBUGGING >>>
            print(f"--- Logging Azure AD login event for user: {username} ---")
            # <<< END DEBUGGING >>>
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

        print("--- Redirecting to dashboard after Azure AD login ---")
        return redirect(url_for('main.dashboard'))

    except ValueError as e:
         print(f"Authentication callback ValueError: {e}")
         flash(f"Login failed: {e}", 'error')
         print("--- Redirecting to login due to ValueError in callback ---")
         return redirect(url_for('main.login'))
    except Exception as e:
         print(f"Unexpected error during Azure AD callback: {e}")
         import traceback
         traceback.print_exc()
         flash("An unexpected error occurred during login.", 'error')
         print("--- Redirecting to login due to unexpected exception in callback ---")
         return redirect(url_for('main.login'))


# --- Dashboard Route ---
@main_bp.route('/dashboard')
@validate_session # Make sure this decorator is correctly applied/imported
def dashboard():
    # <<< DEBUGGING >>>
    print(f"--- Request received for /dashboard from {request.remote_addr} ---")
    # <<< END DEBUGGING >>>
    stats = { 'facilities': 0, 'production_lines': 0, 'recent_downtime_count': 0, 'categories': 0 }
    try:
        stats['facilities'] = len(facilities_db.get_all(active_only=True) or [])
        stats['production_lines'] = len(lines_db.get_all(active_only=True) or [])
        stats['categories'] = len(categories_db.get_all(active_only=True) or [])
        stats['recent_downtime_count'] = len(downtimes_db.get_recent(days=7) or [])
    except Exception as e: print(f"Error getting dashboard stats: {e}")

    print("--- Rendering dashboard template ---")
    return render_template('dashboard.html', user=session.get('user'), stats=stats, config=Config)


# --- Logout Route ---
@main_bp.route('/logout')
def logout():
    # <<< DEBUGGING >>>
    print(f"--- Request received for /logout from {request.remote_addr} ---")
    # <<< END DEBUGGING >>>
    username = session.get('user', {}).get('username', 'Unknown')
    session_id = session.get('session_id')

    if session_id:
        sessions_db.end_session(session_id)

    # Clear Flask session keys
    session.pop('user', None)
    session.pop('session_id', None)
    session.pop('token_cache', None) # MSAL cache if stored
    session.pop('state', None) # MSAL state

    print(f"User {username} logged out locally.")
    flash(_('You have been successfully logged out'), 'info')

    # Redirect to Azure AD logout endpoint
    logout_uri = url_for('main.index', _external=True) # Redirect back to index/login after Azure logout
    azure_logout_url = (
        f"{Config.AAD_AUTHORITY}/oauth2/v2.0/logout"
        f"?post_logout_redirect_uri={logout_uri}"
    )
    print(f"--- Redirecting to Azure AD logout URL: {azure_logout_url} ---")
    return redirect(azure_logout_url)


# --- Status Route ---
@main_bp.route('/status')
@validate_session # Make sure decorator is applied/imported
def status():
    # <<< DEBUGGING >>>
    print(f"--- Request received for /status from {request.remote_addr} ---")
    # <<< END DEBUGGING >>>
    # Use require_admin check directly
    if not require_admin(session):
        flash(_('Admin privileges required'), 'error')
        return redirect(url_for('main.dashboard'))

    status_info = {
        'db_connected': False,
        'test_mode': Config.TEST_MODE,
        'auth_mode': 'Azure AD (OIDC)', # Updated auth mode description
        'facilities_count': 0,
        'lines_count': 0,
        'users_today': 0, # Consider removing if not used or reliably fetched
        'active_sessions': 0
    }
    try:
        db_conn = sessions_db.db # Access the underlying connection object via sessions_db instance
        status_info['db_connected'] = db_conn.test_connection()
        if status_info['db_connected']:
             status_info['active_sessions'] = sessions_db.get_active_sessions_count()
             status_info['facilities_count'] = len(facilities_db.get_all(active_only=True) or [])
             status_info['lines_count'] = len(lines_db.get_all(active_only=True) or [])
             # stats = users_db.get_login_statistics() # Fetching full stats might be slow
             # status_info['users_today'] = stats.get('active_today', 0)
    except Exception as e: print(f"Error in status check: {e}")

    print("--- Rendering status template ---")
    return render_template('status.html', user=session.get('user'), status=status_info, config=Config)