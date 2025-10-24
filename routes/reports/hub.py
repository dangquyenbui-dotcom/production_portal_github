# routes/reports/hub.py
"""
Route for the main Reports Hub page.
"""
from flask import Blueprint, render_template, redirect, url_for, session, flash
from auth import (
    require_login, require_admin, require_scheduling_admin, require_scheduling_user
)
from routes.main import validate_session

reports_hub_bp = Blueprint('reports_hub', __name__)

# --- Define the required access level for the hub ---
REQUIRED_HUB_ACCESS = lambda s: require_admin(s) or require_scheduling_admin(s) or require_scheduling_user(s)
# --- END MODIFICATION ---

@reports_hub_bp.route('/') # Route is relative to the parent blueprint's prefix ('/reports')
@validate_session
def hub():
    if not require_login(session):
        return redirect(url_for('main.login'))
    # --- Use the broader access check ---
    if not REQUIRED_HUB_ACCESS(session):
        flash('Report viewing privileges are required to access this page.', 'error')
        return redirect(url_for('main.dashboard'))
    # --- END MODIFICATION ---
    return render_template('reports/hub.html', user=session['user'])