# routes/admin/permissions.py
"""
Admin routes for managing user-specific permissions.
"""

from flask import Blueprint, render_template, redirect, url_for, session, jsonify, request, flash
# require_admin is still needed for the *internal* check, but not as a decorator here
from auth import require_login, require_admin, require_portal_admin
from routes.main import validate_session
from database.permissions import permissions_db # Import the new DB class
from database import audit_db
from utils import get_client_info
import traceback
from i18n_config import _ # Import translation


# Use require_portal_admin for permission management access
admin_permissions_bp = Blueprint('admin_permissions', __name__)

@admin_permissions_bp.route('/permissions')
@validate_session
# REMOVE @require_admin from here - the check is done inside the function
def manage_permissions():
    """Display the user permissions management page."""
    # This internal check is correct
    if not (session['user'].get('is_portal_admin') or session['user'].get('username') == 'production_portal_admin'):
         flash(_('Only Portal Administrators can manage permissions.'), 'error')
         # Redirect to the main admin panel, not dashboard if already in admin area
         return redirect(url_for('admin_panel.panel'))

    try:
        users = permissions_db.get_users_with_permissions()
        # Sort users by username for consistent display
        users.sort(key=lambda u: u.get('username', '').lower()) # Add .get for safety
    except Exception as e:
        flash(f"Error fetching user permissions: {e}", "error")
        traceback.print_exc()
        users = []

    return render_template(
        'admin/permissions.html',
        user=session['user'],
        all_users_permissions=users
    )

@admin_permissions_bp.route('/permissions/update', methods=['POST'])
@validate_session
# REMOVE @require_admin from here - the check is done inside the function
def update_permissions():
    """API endpoint to update permissions for a single user."""
    # This internal check is correct
    if not (session['user'].get('is_portal_admin') or session['user'].get('username') == 'production_portal_admin'):
        return jsonify({'success': False, 'message': _('Unauthorized')}), 403

    try:
        data = request.get_json()
        target_username = data.get('username')
        permissions = data.get('permissions', {})

        if not target_username:
            return jsonify({'success': False, 'message': _('Username is required.')}), 400

        # Validate and structure permissions
        valid_permissions = {}
        # Define valid keys based on your UserPermissions table columns
        valid_keys = ['can_view_scheduling', 'can_edit_scheduling', 'can_view_downtime', 'can_view_reports']
        changes_log = {} # For audit log

        # Get current permissions for comparison
        current_perms = permissions_db.get_user_permissions(target_username)

        for key in valid_keys:
            new_value = bool(permissions.get(key, False)) # Ensure boolean
            valid_permissions[key] = new_value
            # Log change if value is different
            current_value = current_perms.get(key, False) # Default to False if not present
            if current_value != new_value:
                # Store boolean values for logging, convert to string later
                changes_log[key] = {'old': current_value, 'new': new_value}


        if not valid_permissions:
             return jsonify({'success': False, 'message': _('No valid permission data provided.')}), 400

        updated_by_user = session['user']['username']
        success, message = permissions_db.update_user_permissions(target_username, valid_permissions, updated_by_user)

        # Log to audit trail if successful and changes occurred
        if success and changes_log:
             ip, user_agent = get_client_info()
             # Convert boolean changes to string for audit log
             string_changes = {k: {'old': str(v['old']), 'new': str(v['new'])} for k, v in changes_log.items()}

             audit_db.log(
                 table_name='UserPermissions',
                 record_id=None, # Record ID is not directly applicable here, using username in notes
                 action_type='UPDATE',
                 changes=string_changes,
                 username=updated_by_user,
                 ip=ip,
                 user_agent=user_agent,
                 notes=f"Permissions updated for user: {target_username}"
             )

        return jsonify({'success': success, 'message': message})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'An internal server error occurred: {e}'}), 500