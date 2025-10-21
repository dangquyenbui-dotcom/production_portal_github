# routes/mrp.py
"""
MRP (Material Requirements Planning) Viewer routes.
UPDATED: Granted Scheduling_User access to main MRP view.
"""

from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify, send_file
# --- MODIFIED: Import require_scheduling_user ---
from auth import require_login, require_admin, require_scheduling_admin, require_scheduling_user
from routes.main import validate_session
# Correctly imports the MRP service, which internally uses the ERP service
from database.mrp_service import mrp_service
import openpyxl
from io import BytesIO
from datetime import datetime

mrp_bp = Blueprint('mrp', __name__, url_prefix='/mrp')

@mrp_bp.route('/')
@validate_session
def view_mrp():
    """Renders the main MRP results page."""
    # --- MODIFIED: Allow Scheduling_User access ---
    if not (require_scheduling_admin(session) or require_scheduling_user(session)):
        flash('MRP access requires Scheduling Admin or Scheduling User privileges.', 'error')
        return redirect(url_for('main.dashboard'))

    try:
        mrp_results = mrp_service.calculate_mrp_suggestions()
    except Exception as e:
        flash(f'An error occurred while running the MRP calculation: {e}', 'error')
        mrp_results = []

    return render_template(
        'mrp/index.html',
        user=session.get('user'), # Pass user safely
        mrp_results=mrp_results
    )

@mrp_bp.route('/summary')
@validate_session
def customer_summary():
    """Renders the customer-specific MRP summary page."""
    # Access restricted to Scheduling Admins only as per matrix
    if not require_scheduling_admin(session):
        flash('MRP Customer Summary access is restricted to Scheduling Admins.', 'error')
        return redirect(url_for('main.dashboard'))

    try:
        mrp_results = mrp_service.calculate_mrp_suggestions()
        all_customers = sorted(list(set(r['sales_order']['Customer Name'] for r in mrp_results if r.get('sales_order') and r['sales_order'].get('Customer Name')))) # Safer access

        selected_customer = request.args.get('customer')
        summary_data = None
        orders_for_template = []

        if selected_customer:
            customer_orders = [r for r in mrp_results if r.get('sales_order') and r['sales_order'].get('Customer Name') == selected_customer] # Safer access
            summary_data = mrp_service.get_customer_summary(customer_orders)
            if summary_data:
                orders_for_template = summary_data.get('orders', [])

    except Exception as e:
        flash(f'An error occurred while generating the summary: {e}', 'error')
        all_customers = []
        selected_customer = None
        summary_data = None
        orders_for_template = []

    filters = { # Keep filters even if no customer selected
        'bu': request.args.get('bu'),
        'fg': request.args.get('fg'),
        'due_ship': request.args.get('due_ship'),
        'status': request.args.get('status')
    }

    return render_template(
        'mrp/summary.html',
        user=session.get('user'),
        customers=all_customers,
        selected_customer=selected_customer,
        summary=summary_data,
        all_orders=orders_for_template,
        filters=filters
    )

@mrp_bp.route('/buyer-view')
@validate_session
def buyer_view():
    """Renders a consolidated view of all component shortages for buyers."""
    # Access check: Includes Scheduling User and Admins (already correct)
    if not (require_scheduling_admin(session) or require_scheduling_user(session)):
        flash('Purchasing access is required to view this page.', 'error')
        return redirect(url_for('main.dashboard'))

    try:
        data = mrp_service.get_consolidated_shortages()
        shortages = data.get('shortages', [])
        customers = data.get('customers', [])
    except Exception as e:
        flash(f'An error occurred while calculating shortages: {e}', 'error')
        shortages = []
        customers = []

    return render_template(
        'mrp/buyer_view.html',
        user=session.get('user'),
        shortages=shortages,
        customers=customers
    )

@mrp_bp.route('/api/export-shortages-xlsx', methods=['POST'])
@validate_session
def export_shortages_xlsx():
    """API endpoint to export the consolidated shortages data to an XLSX file."""
    # Access check: Includes Scheduling User and Admins (already correct)
    if not (require_scheduling_admin(session) or require_scheduling_user(session)):
        return jsonify({'success': False, 'message': 'Authentication required'}), 401

    try:
        data = request.get_json()
        headers = data.get('headers', [])
        rows = data.get('rows', [])

        if not headers or not rows:
            return jsonify({'success': False, 'message': 'No data to export'}), 400

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "MRP Shortage Report"
        ws.append(headers)

        for row_data in rows:
            processed_row = []
            for item in row_data:
                try:
                    num_val = float(item.replace(',', ''))
                    processed_row.append(num_val)
                except (ValueError, TypeError):
                    processed_row.append(item)
            ws.append(processed_row)


        output = BytesIO()
        wb.save(output)
        output.seek(0)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"mrp_shortage_report_{timestamp}.xlsx"

        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        print(f"Error exporting MRP shortages: {e}")
        return jsonify({'success': False, 'message': 'An error occurred during export.'}), 500

@mrp_bp.route('/api/export-xlsx', methods=['POST'])
@validate_session
def export_mrp_xlsx():
    """API endpoint to export the visible MRP data to an XLSX file."""
    # --- MODIFIED: Check broadened to include Scheduling User for export ---
    if not (require_scheduling_admin(session) or require_scheduling_user(session)):
        return jsonify({'success': False, 'message': 'Scheduling privileges required for this export'}), 403

    try:
        data = request.get_json()
        headers = data.get('headers', [])
        rows = data.get('rows', [])

        if not headers or not rows:
            return jsonify({'success': False, 'message': 'No data to export'}), 400

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "MRP Export"
        ws.append(headers)

        for row_data in rows:
            processed_row = []
            for item in row_data:
                try:
                    num_val = float(item.replace(',', ''))
                    processed_row.append(num_val)
                except (ValueError, TypeError):
                    processed_row.append(item)
            ws.append(processed_row)


        output = BytesIO()
        wb.save(output)
        output.seek(0)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"mrp_export_{timestamp}.xlsx"

        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        print(f"Error exporting MRP: {e}")
        return jsonify({'success': False, 'message': 'An error occurred during export.'}), 500