# routes/reports/downtime_summary.py
"""
Route for the Downtime Summary Report.
"""
from flask import Blueprint, render_template, redirect, url_for, session, request, flash
from auth import (
    require_login, require_admin, require_scheduling_admin, require_scheduling_user
)
from routes.main import validate_session
from database import facilities_db, lines_db, reports_db
from datetime import datetime, timedelta

downtime_summary_bp = Blueprint('downtime_summary', __name__)

# --- Define the required access level for reports ---
REQUIRED_REPORT_ACCESS = lambda s: require_admin(s) or require_scheduling_admin(s) or require_scheduling_user(s)
# --- END MODIFICATION ---

@downtime_summary_bp.route('/downtime-summary')
@validate_session
def downtime_summary():
    if not require_login(session):
        return redirect(url_for('main.login'))
    # --- Use the broader access check ---
    if not REQUIRED_REPORT_ACCESS(session):
        flash('Report viewing privileges are required to view reports.', 'error')
        return redirect(url_for('main.dashboard'))
    # --- END MODIFICATION ---

    today = datetime.now()
    start_date_str = request.args.get('start_date', (today - timedelta(days=7)).strftime('%Y-%m-%d'))
    end_date_str = request.args.get('end_date', today.strftime('%Y-%m-%d'))
    facility_id = request.args.get('facility_id', type=int)
    line_id = request.args.get('line_id', type=int)

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)

        report_data = reports_db.get_downtime_summary(
            start_date=start_date, end_date=end_date,
            facility_id=facility_id, line_id=line_id
        )
        facilities = facilities_db.get_all(active_only=True)
        lines = lines_db.get_by_facility(facility_id=facility_id, active_only=True) if facility_id else []

        return render_template(
            'reports/downtime_summary.html',
            user=session['user'], report_data=report_data,
            filters={'start_date': start_date_str, 'end_date': end_date_str, 'facility_id': facility_id, 'line_id': line_id},
            facilities=facilities, lines=lines
        )
    except ValueError:
        flash('Invalid date format provided.', 'error')
        # Provide default data structure on error
        report_data = {
            'overall_stats': {'total_events': 0, 'total_minutes': 0, 'avg_duration': 0},
            'by_category': [], 'by_line': [], 'raw_data': []
        }
        facilities = facilities_db.get_all(active_only=True)
        lines = []
        return render_template(
            'reports/downtime_summary.html',
            user=session['user'], report_data=report_data,
            filters={'start_date': start_date_str, 'end_date': end_date_str, 'facility_id': facility_id, 'line_id': line_id},
            facilities=facilities, lines=lines
        )
    except Exception as e:
        flash(f'An error occurred generating the report: {e}', 'error')
        # Provide default data structure on error
        report_data = {
            'overall_stats': {'total_events': 0, 'total_minutes': 0, 'avg_duration': 0},
            'by_category': [], 'by_line': [], 'raw_data': []
        }
        facilities = facilities_db.get_all(active_only=True)
        lines = []
        return render_template(
            'reports/downtime_summary.html',
            user=session['user'], report_data=report_data,
            filters={'start_date': start_date_str, 'end_date': end_date_str, 'facility_id': facility_id, 'line_id': line_id},
            facilities=facilities, lines=lines
        )