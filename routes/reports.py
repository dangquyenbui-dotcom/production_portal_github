# routes/reports.py
"""
Reporting routes for generating and viewing system reports.
CORRECTED: Updated permission checks to align with the matrix.
FIXED: CoC report aggregation key to combine rows with null/empty lot/exp date.
"""
from flask import (
    Blueprint, render_template, redirect, url_for, session, request, flash, send_file,
    current_app
)
# --- MODIFIED: Import more specific permission checkers ---
from auth import (
    require_login, require_admin, require_scheduling_admin, require_scheduling_user
)
# --- END MODIFICATION ---
from routes.main import validate_session
from database import facilities_db, lines_db, get_erp_service
from database.reports import reports_db
from datetime import datetime, timedelta
import traceback
from collections import OrderedDict
import io
from utils.pdf_generator import generate_coc_pdf

# Helper function
def safe_float(value, default=0.0):
    """Safely convert value to float, handling None and potential errors."""
    if value is None: return default
    try: return float(value)
    except (TypeError, ValueError): return default

# Helper function to format dates
def _format_date(date_obj, date_format='%m/%d/%Y', default='N/A'): # Format: MM/DD/YYYY
    """Safely format a datetime object, handling None."""
    if date_obj is None:
        return default
    try:
        # Check for common default/invalid dates from ERP if necessary
        if isinstance(date_obj, datetime) and date_obj.year <= 1900:
            return default
        return date_obj.strftime(date_format)
    except (AttributeError, ValueError): # Added ValueError for invalid date objects
        return default

# ***** HELPER FUNCTION for CoC Report *****
def _get_single_job_details(job_number_str):
    """Fetches and processes data for a single job for the CoC report."""
    if not job_number_str:
        return None

    erp_service = get_erp_service()
    raw_data = erp_service.get_coc_report_data(job_number_str)

    if not raw_data or not raw_data.get("header"):
        return {'error': f"Job '{job_number_str}' not found in the ERP system."}

    header = raw_data["header"]
    fifo_details = raw_data.get("fifo_details", [])
    relieve_details = raw_data.get("relieve_details", [])

    job_data = {
        'job_number': str(header['jo_jobnum']),
        'part_number': header.get('part_number', ''),
        'part_description': header.get('part_description', ''),
        'customer_name': header.get('customer_name', 'N/A'),
        'sales_order': str(header.get('sales_order_number', '')) if header.get('sales_order_number') else '',
        'required_qty': safe_float(header.get('required_quantity')),
        'completed_qty': 0.0,
        'aggregated_transactions': {}
    }

    finish_job_entries = []
    other_fifo_entries = []

    # Map fi_id to lot and formatted expiration date for relieve linking
    fi_id_to_details_map = {
        row.get('fi_id'): {
            'lot_number': row.get('lot_number', ''), # Already normalized to '' if NULL by query
            'exp_date_raw': row.get('fi_expires') # Store raw date
        }
        for row in fifo_details if row.get('fi_id')
    }

    # Process FIFO details first
    for row in fifo_details:
        action = row.get('fi_action')
        timestamp = row.get('fi_recdate')
        quantity = safe_float(row.get('fi_quant'))

        # Separate 'Finish Job' transactions
        if action == 'Finish Job' and timestamp:
            finish_job_entries.append({'timestamp': timestamp, 'quantity': quantity})
            job_data['completed_qty'] += quantity
        else:
            # Aggregate other FIFO transactions
            part_num = row.get('part_number', '')
            part_desc = row.get('part_description', '')
            # --- MODIFICATION START: Normalize key components ---
            raw_lot_num = row.get('lot_number', '') # Query defaults NULL to ''
            normalized_lot_num = raw_lot_num if raw_lot_num else 'N/A' # Use 'N/A' for empty/null lots in key

            raw_exp_date = row.get('fi_expires')
            formatted_exp_date = _format_date(raw_exp_date) # Format FIRST
            normalized_exp_date = formatted_exp_date # Use the formatted string ('N/A' or date) in key
            
            agg_key = (part_num, normalized_lot_num, normalized_exp_date)
            # --- MODIFICATION END ---

            if not part_num: continue

            if agg_key not in job_data['aggregated_transactions']:
                job_data['aggregated_transactions'][agg_key] = {
                    'part_number': part_num,
                    'part_description': part_desc,
                    'lot_number': normalized_lot_num, # Store normalized version
                    'exp_date': normalized_exp_date, # Store normalized version
                    'Starting Lot Qty': 0.0,
                    'Ending Inventory': 0.0,
                    'Packaged Qty': 0.0,
                    'Yield Cost/Scrap': 0.0,
                    'Yield Loss': 0.0
                }
            # Update description if it was missing initially
            if not job_data['aggregated_transactions'][agg_key].get('part_description') and part_desc:
                 job_data['aggregated_transactions'][agg_key]['part_description'] = part_desc

            # Aggregate quantities based on action
            if action == 'Issued inventory':
                job_data['aggregated_transactions'][agg_key]['Starting Lot Qty'] += quantity
            elif action == 'De-issue':
                job_data['aggregated_transactions'][agg_key]['Ending Inventory'] += quantity
            # Handle other FIFO actions if necessary

    # Sort 'Finish Job' entries chronologically
    finish_job_entries.sort(key=lambda x: x['timestamp'])

    # Process Relieve Job transactions (dtfifo2) chronologically up to each 'Finish Job' timestamp
    relieve_pointer = 0
    processed_relieve_ids = set()

    for fj_entry in finish_job_entries:
        fj_timestamp = fj_entry['timestamp']

        for i in range(relieve_pointer, len(relieve_details)):
            relieve_row = relieve_details[i]
            relieve_timestamp = relieve_row.get('f2_recdate')
            relieve_id = relieve_row.get('f2_id') # Unique ID for dtfifo2 row

            if relieve_id is None:
                print(f"Warning: Relieve transaction missing unique ID: {relieve_row}")
                continue # Skip if we can't uniquely identify

            # Process relieve transactions that occurred up to or at the same time as the current Finish Job
            if relieve_timestamp and relieve_timestamp <= fj_timestamp:
                # Ensure we haven't already processed this specific relieve transaction ID
                if relieve_id not in processed_relieve_ids:
                    part_num = relieve_row.get('part_number', '')
                    part_desc = relieve_row.get('part_description', '')
                    quantity = safe_float(relieve_row.get('net_quantity')) # Use net_quantity from query

                    # Link back to the original FIFO entry to get lot/exp date
                    linked_fi_id = relieve_row.get('f2_fiid')
                    details = fi_id_to_details_map.get(linked_fi_id, {'lot_number': '', 'exp_date_raw': None})

                    # --- MODIFICATION START: Normalize key components ---
                    raw_lot_num = details['lot_number'] # Already normalized to '' if NULL by query
                    normalized_lot_num = raw_lot_num if raw_lot_num else 'N/A'

                    raw_exp_date = details['exp_date_raw']
                    formatted_exp_date = _format_date(raw_exp_date) # Format FIRST
                    normalized_exp_date = formatted_exp_date

                    agg_key = (part_num, normalized_lot_num, normalized_exp_date)
                    # --- MODIFICATION END ---


                    if not part_num: continue

                    # Initialize aggregation dictionary if key doesn't exist
                    if agg_key not in job_data['aggregated_transactions']:
                        job_data['aggregated_transactions'][agg_key] = {
                            'part_number': part_num,
                            'part_description': part_desc,
                            'lot_number': normalized_lot_num, # Store normalized version
                            'exp_date': normalized_exp_date, # Store normalized version
                            'Starting Lot Qty': 0.0,
                            'Ending Inventory': 0.0,
                            'Packaged Qty': 0.0,
                            'Yield Cost/Scrap': 0.0,
                            'Yield Loss': 0.0
                        }
                     # Update description if it was missing initially
                    if not job_data['aggregated_transactions'][agg_key].get('part_description') and part_desc:
                         job_data['aggregated_transactions'][agg_key]['part_description'] = part_desc

                    # Add the relieved quantity to 'Packaged Qty'
                    job_data['aggregated_transactions'][agg_key]['Packaged Qty'] += quantity
                    processed_relieve_ids.add(relieve_id) # Mark this specific transaction ID as processed

                # Move the pointer forward ONLY if this transaction was processed
                # (prevents infinite loop if multiple transactions have same timestamp)
                if relieve_id in processed_relieve_ids:
                    relieve_pointer = i + 1

            elif relieve_timestamp and relieve_timestamp > fj_timestamp:
                 # Stop processing relieve transactions for this 'Finish Job' timestamp
                 break # Go to the next 'Finish Job' entry

    # Calculate Yields after all transactions are aggregated
    for agg_key, summary in job_data['aggregated_transactions'].items():
        issued = summary.get('Starting Lot Qty', 0.0)
        relieve = summary.get('Packaged Qty', 0.0) # This now includes dtfifo2 'Relieve Job'
        deissue = summary.get('Ending Inventory', 0.0)
        yield_cost = issued - relieve - deissue
        summary['Yield Cost/Scrap'] = yield_cost
        # Prevent division by zero
        summary['Yield Loss'] = (yield_cost / relieve) * 100.0 if relieve != 0 else 0.0

    # Create the final list for display, filtering out unwanted parts
    job_data['aggregated_list'] = [
        summary for summary in job_data['aggregated_transactions'].values()
        # Filter out 0800- parts AND the main finished good itself
        if not summary.get('part_number', '').startswith('0800-')
           and summary.get('part_number', '') != job_data['part_number']
    ]
    # Sort the final list
    job_data['aggregated_list'].sort(key=lambda x: (
        x.get('part_number', ''),
        x.get('lot_number', ''), # Sorting by 'N/A' or actual lot
        x.get('exp_date', '')   # Sorting by 'N/A' or actual formatted date
    ))

    # Group by part number for display (no changes needed here)
    grouped_list = OrderedDict()
    for summary in job_data['aggregated_list']:
        part_num = summary.get('part_number', '')
        if part_num not in grouped_list:
            grouped_list[part_num] = {
                'part_description': summary.get('part_description', ''),
                'lots': []
            }
        grouped_list[part_num]['lots'].append(summary)

    job_data['grouped_list'] = grouped_list


    # Remove the no longer needed intermediate structure
    del job_data['aggregated_transactions']

    return job_data
# ***** END HELPER FUNCTION *****


reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

# --- MODIFIED: Define the required access level for reports ---
REQUIRED_REPORT_ACCESS = lambda s: require_admin(s) or require_scheduling_admin(s) or require_scheduling_user(s)
# --- END MODIFICATION ---

@reports_bp.route('/')
@validate_session # Use validate_session decorator
def hub():
    if not require_login(session):
        return redirect(url_for('main.login'))
    # --- MODIFIED: Use the broader access check ---
    if not REQUIRED_REPORT_ACCESS(session):
        flash('Report viewing privileges are required to access this page.', 'error')
        return redirect(url_for('main.dashboard'))
    # --- END MODIFICATION ---
    return render_template('reports/hub.html', user=session['user'])

@reports_bp.route('/downtime-summary')
@validate_session # Use validate_session decorator
def downtime_summary():
    if not require_login(session):
        return redirect(url_for('main.login'))
    # --- MODIFIED: Use the broader access check ---
    if not REQUIRED_REPORT_ACCESS(session):
        flash('Report viewing privileges are required to view reports.', 'error')
        return redirect(url_for('main.dashboard'))
    # --- END MODIFICATION ---

    today = datetime.now()
    start_date_str = request.args.get('start_date', (today - timedelta(days=7)).strftime('%Y-%m-%d'))
    end_date_str = request.args.get('end_date', today.strftime('%Y-%m-%d'))
    facility_id = request.args.get('facility_id', type=int)
    line_id = request.args.get('line_id', type=int)

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

@reports_bp.route('/shipment-forecast')
@validate_session # Use validate_session decorator
def shipment_forecast():
    if not require_login(session):
        return redirect(url_for('main.login'))
    # --- MODIFIED: Use the broader access check ---
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

@reports_bp.route('/coc', methods=['GET'])
@validate_session
def coc_report():
    if not require_login(session): # Added login check
        return redirect(url_for('main.login'))
    # --- MODIFIED: Use the broader access check ---
    if not REQUIRED_REPORT_ACCESS(session):
        flash('Report viewing privileges are required to view this report.', 'error')
        return redirect(url_for('main.dashboard'))
    # --- END MODIFICATION ---

    job_number_param = request.args.get('job_number', '').strip()
    job_details = None
    error_message = None

    if job_number_param:
        try:
            job_details = _get_single_job_details(job_number_param)
            if job_details and 'error' in job_details:
                error_message = job_details['error']
                job_details = None
        except Exception as e:
            flash(f'An error occurred while fetching job details: {e}', 'error')
            traceback.print_exc()
            error_message = f"An unexpected error occurred: {str(e)}"
            job_details = None

    return render_template(
        'reports/coc.html',
        user=session['user'],
        job_number=job_number_param,
        job_details=job_details,
        error_message=error_message
    )

@reports_bp.route('/coc/pdf', methods=['GET'])
@validate_session
def coc_report_pdf():
    """
    Generates and serves a PDF version of the CoC report.
    """
    if not require_login(session): # Added login check
        return redirect(url_for('main.login'))
    # --- MODIFIED: Use the broader access check ---
    if not REQUIRED_REPORT_ACCESS(session):
        flash('Report viewing privileges are required to export reports.', 'error')
        return redirect(url_for('main.dashboard'))
    # --- END MODIFICATION ---

    job_number_param = request.args.get('job_number', '').strip()
    if not job_number_param:
        flash('A Job Number is required to generate a PDF.', 'error')
        return redirect(url_for('reports.coc_report'))

    try:
        # Get the same data as the web page
        job_details = _get_single_job_details(job_number_param)

        if not job_details or 'error' in job_details:
            error_message = job_details.get('error', 'Job not found')
            flash(f'Could not generate PDF: {error_message}', 'error')
            return redirect(url_for('reports.coc_report', job_number=job_number_param))

        app_root_path = current_app.root_path

        # Generate the PDF
        pdf_buffer, filename = generate_coc_pdf(job_details, app_root_path)

        # Send the PDF as a file download
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )

    except Exception as e:
        flash(f'An error occurred while generating the PDF: {e}', 'error')
        traceback.print_exc()
        return redirect(url_for('reports.coc_report', job_number=job_number_param))