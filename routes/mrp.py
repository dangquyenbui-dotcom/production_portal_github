# routes/mrp.py
"""
MRP (Material Requirements Planning) Viewer routes.
MODIFIED: Added Semaphore lock to all heavy query routes.
"""

from flask import (Blueprint, render_template, session, redirect, url_for, 
                   flash, request, jsonify, send_file, current_app) # <-- ADDED current_app
from auth import require_login
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
    if not (session.get('user', {}).get('is_admin') or session.get('user', {}).get('is_scheduling_admin')):
        flash('MRP access is restricted to administrators and scheduling admins.', 'error')
        return redirect(url_for('main.dashboard'))

    # --- ADDED: Acquire Semaphore ---
    heavy_query_semaphore = current_app.heavy_query_semaphore
    current_app.logger.info("MRP view: Waiting to acquire heavy query lock...")
    heavy_query_semaphore.acquire()
    current_app.logger.info("MRP view: Lock acquired. Running heavy query.")
    # --- END ADDED ---

    try:
        mrp_results = mrp_service.calculate_mrp_suggestions()
    except Exception as e:
        flash(f'An error occurred while running the MRP calculation: {e}', 'error')
        mrp_results = []
        current_app.logger.error(f"Error during mrp.view_mrp: {e}")
    finally:
        # --- ADDED: Release Semaphore ---
        heavy_query_semaphore.release()
        current_app.logger.info("MRP view: Lock released.")
    # --- END ADDED ---

    return render_template(
        'mrp/index.html',
        user=session['user'],
        mrp_results=mrp_results
    )

@mrp_bp.route('/summary')
@validate_session
def customer_summary():
    """Renders the customer-specific MRP summary page with full filtering."""
    if not (session.get('user', {}).get('is_admin') or session.get('user', {}).get('is_scheduling_admin')):
        flash('MRP access is restricted.', 'error')
        return redirect(url_for('main.dashboard'))

    # --- ADDED: Acquire Semaphore ---
    heavy_query_semaphore = current_app.heavy_query_semaphore
    current_app.logger.info("MRP summary: Waiting to acquire heavy query lock...")
    heavy_query_semaphore.acquire()
    current_app.logger.info("MRP summary: Lock acquired. Running heavy query.")
    # --- END ADDED ---

    try:
        mrp_results = mrp_service.calculate_mrp_suggestions()
        all_customers = sorted(list(set(r['sales_order']['Customer Name'] for r in mrp_results)))

        selected_customer = request.args.get('customer')
        summary_data = None
        orders_for_template = []

        if selected_customer:
            customer_orders = [r for r in mrp_results if r['sales_order']['Customer Name'] == selected_customer]
            summary_data = mrp_service.get_customer_summary(customer_orders)
            if summary_data:
                orders_for_template = summary_data.get('orders', [])

    except Exception as e:
        flash(f'An error occurred while generating the summary: {e}', 'error')
        all_customers = []
        selected_customer = None
        summary_data = None
        orders_for_template = []
        current_app.logger.error(f"Error during mrp.customer_summary: {e}")
    finally:
        # --- ADDED: Release Semaphore ---
        heavy_query_semaphore.release()
        current_app.logger.info("MRP summary: Lock released.")
    # --- END ADDED ---

    filters = {
        'bu': request.args.get('bu'),
        'fg': request.args.get('fg'),
        'due_ship': request.args.get('due_ship'),
        'status': request.args.get('status')
    }

    return render_template(
        'mrp/summary.html',
        user=session['user'],
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
    if not (session.get('user', {}).get('is_admin')
            or session.get('user', {}).get('is_scheduling_admin')
            or session.get('user', {}).get('is_scheduling_user')):
        flash('Purchasing access is required to view this page.', 'error')
        return redirect(url_for('main.dashboard'))

    # --- ADDED: Acquire Semaphore ---
    heavy_query_semaphore = current_app.heavy_query_semaphore
    current_app.logger.info("MRP buyer-view: Waiting to acquire heavy query lock...")
    heavy_query_semaphore.acquire()
    current_app.logger.info("MRP buyer-view: Lock acquired. Running heavy query.")
    # --- END ADDED ---

    try:
        data = mrp_service.get_consolidated_shortages()
        shortages = data.get('shortages', [])
        customers = data.get('customers', [])
    except Exception as e:
        flash(f'An error occurred while calculating shortages: {e}', 'error')
        shortages = []
        customers = []
        current_app.logger.error(f"Error during mrp.buyer_view: {e}")
    finally:
        # --- ADDED: Release Semaphore ---
        heavy_query_semaphore.release()
        current_app.logger.info("MRP buyer-view: Lock released.")
    # --- END ADDED ---

    return render_template(
        'mrp/buyer_view.html',
        user=session['user'],
        shortages=shortages,
        customers=customers
    )

@mrp_bp.route('/api/export-shortages-xlsx', methods=['POST'])
@validate_session
def export_shortages_xlsx():
    # ... (This route is fast, no changes needed) ...
    """API endpoint to export the consolidated shortages data to an XLSX file."""
    if not (session.get('user', {}).get('is_admin')
            or session.get('user', {}).get('is_scheduling_admin')
            or session.get('user', {}).get('is_scheduling_user')):
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
            ws.append(row_data)

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
    # ... (This route is fast, no changes needed) ...
    """API endpoint to export the visible MRP data to an XLSX file."""
    if not (session.get('user', {}).get('is_admin') or session.get('user', {}).get('is_scheduling_admin')):
        return jsonify({'success': False, 'message': 'Authentication required'}), 401

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
            ws.append(row_data)

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"mrp_export_{timestamp}.xlsx" # Corrected filename typo

        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        print(f"Error exporting MRP: {e}")
        return jsonify({'success': False, 'message': 'An error occurred during export.'}), 500