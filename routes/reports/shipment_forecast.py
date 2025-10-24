# routes/reports/shipment_forecast.py
"""
Route for the Shipment Forecast Report.
"""
from flask import Blueprint, render_template, redirect, url_for, session, flash
from auth import (
    require_login, require_admin, require_scheduling_admin, require_scheduling_user
)
from routes.main import validate_session
from database import reports_db # Assuming reports_db handles the forecast logic
from datetime import datetime

shipment_forecast_bp = Blueprint('shipment_forecast', __name__)

# --- Define the required access level for reports ---
REQUIRED_REPORT_ACCESS = lambda s: require_admin(s) or require_scheduling_admin(s) or require_scheduling_user(s)
# --- END MODIFICATION ---

@shipment_forecast_bp.route('/shipment-forecast')
@validate_session
def shipment_forecast():
    if not require_login(session):
        return redirect(url_for('main.login'))
    # --- Use the broader access check ---
    if not REQUIRED_REPORT_ACCESS(session):
        flash('Report viewing privileges are required to view reports.', 'error')
        return redirect(url_for('main.dashboard'))
    # --- END MODIFICATION ---
    try:
        forecast_data = reports_db.get_shipment_forecast()
    except Exception as e:
        flash(f'An error occurred while generating the forecast: {e}', 'error')
        forecast_data = {'month_name': datetime.now().strftime('%B %Y'), 'likely_total_value': 0, 'at_risk_total_value': 0, 'likely_orders': [], 'at_risk_orders': []}
    return render_template('reports/shipment_forecast.html', user=session['user'], forecast=forecast_data)