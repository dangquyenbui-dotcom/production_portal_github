# routes/reports/coc.py
"""
Route for the Certificate of Compliance (CoC) Report.
CORRECTED: Updated permission checks to align with the matrix.
FIXED: CoC report aggregation key to combine rows with null/empty lot/exp date.
FIXED: More robust lot number normalization in CoC report aggregation.
FIXED: Relieve Job aggregation to use existing lot if linked FIFO record lacks one.
MODIFIED: Include 'Un-relieve Job' from dtfifo in Packaged Qty calculation.
MODIFIED: Correctly subtract 'Un-finish Job' quantity from dtfifo2 in completed_qty calculation.
REMOVED: All debug print statements.
MODIFIED: Strip hyphens from job_number input in routes.
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
from database import get_erp_service
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
    # Pass the cleaned job number string to the service
    raw_data = erp_service.get_coc_report_data(job_number_str)

    if not raw_data or not raw_data.get("header"):
        return {'error': f"Job '{job_number_str}' not found in the ERP system."}

    header = raw_data["header"]
    fifo_details = raw_data.get("fifo_details", [])
    relieve_details = raw_data.get("relieve_details", []) # Data from dtfifo2 (now includes Un-finish Job)

    job_data = {
        'job_number': str(header['jo_jobnum']),
        'part_number': header.get('part_number', ''),
        'part_description': header.get('part_description', ''),
        'customer_name': header.get('customer_name', 'N/A'),
        'sales_order': str(header.get('sales_order_number', '')) if header.get('sales_order_number') else '',
        'required_qty': safe_float(header.get('required_quantity')),
        'completed_qty': 0.0, # Initial value - will be adjusted by dtfifo and dtfifo2
        'aggregated_transactions': {}
    }

    finish_job_entries = [] # Keep track for chronological processing later

    # Map fi_id to lot and formatted expiration date for relieve linking
    fi_id_to_details_map = {
        row.get('fi_id'): {
            'lot_number': row.get('lot_number', ''), # Already normalized to '' if NULL by query
            'exp_date_raw': row.get('fi_expires') # Store raw date
        }
        for row in fifo_details if row.get('fi_id')
    }

    # --- Step 1: Calculate initial completed_qty sum from dtfifo 'Finish Job' ---
    for row in fifo_details:
        action = row.get('fi_action')
        timestamp = row.get('fi_recdate')
        quantity = safe_float(row.get('fi_quant'))
        fi_id = row.get('fi_id')

        if action == 'Finish Job' and timestamp:
            finish_job_entries.append({'timestamp': timestamp, 'quantity': quantity})
            job_data['completed_qty'] += quantity # Accumulate positive values
        # --- Handle other dtfifo actions for the aggregation table (not completed_qty) ---
        else:
            part_num = row.get('part_number', '')
            part_desc = row.get('part_description', '')
            raw_lot_num = row.get('lot_number', '')
            stripped_lot_num = raw_lot_num.strip() if raw_lot_num else ''
            normalized_lot_num = stripped_lot_num if stripped_lot_num else 'N/A'
            raw_exp_date = row.get('fi_expires')
            formatted_exp_date = _format_date(raw_exp_date)
            normalized_exp_date = formatted_exp_date
            agg_key = (part_num, normalized_lot_num, normalized_exp_date)

            if not part_num: continue

            if agg_key not in job_data['aggregated_transactions']:
                job_data['aggregated_transactions'][agg_key] = {
                    'part_number': part_num, 'part_description': part_desc,
                    'lot_number': normalized_lot_num, 'exp_date': normalized_exp_date,
                    'Starting Lot Qty': 0.0, 'Ending Inventory': 0.0, 'Packaged Qty': 0.0,
                    'Yield Cost/Scrap': 0.0, 'Yield Loss': 0.0, '_UnRelieveJobQty': 0.0
                }
            if not job_data['aggregated_transactions'][agg_key].get('part_description') and part_desc:
                 job_data['aggregated_transactions'][agg_key]['part_description'] = part_desc

            if action == 'Issued inventory':
                job_data['aggregated_transactions'][agg_key]['Starting Lot Qty'] += quantity
            elif action == 'De-issue':
                job_data['aggregated_transactions'][agg_key]['Ending Inventory'] += quantity
            elif action == 'Un-relieve Job':
                job_data['aggregated_transactions'][agg_key]['_UnRelieveJobQty'] += quantity

    # --- Step 2: Adjust completed_qty based on dtfifo2 'Un-finish Job' ---
    for relieve_row in relieve_details: # Iterate through dtfifo2 data
        action = relieve_row.get('f2_action')
        relieve_id = relieve_row.get('f2_id')
        quantity_adjustment = safe_float(relieve_row.get('net_quantity'))

        if action == 'Un-finish Job':
             job_data['completed_qty'] -= quantity_adjustment # Subtract the adjustment

    # Sort 'Finish Job' entries (from dtfifo) chronologically for relieve processing loop
    finish_job_entries.sort(key=lambda x: x['timestamp'])

    # --- Step 3: Process dtfifo2 transactions chronologically *for the aggregation table* ---
    # This loop focuses on 'Relieve Job' for Packaged Qty
    relieve_pointer = 0
    processed_relieve_ids = set()

    for fj_entry in finish_job_entries:
        fj_timestamp = fj_entry['timestamp']

        for i in range(relieve_pointer, len(relieve_details)):
            relieve_row = relieve_details[i]
            relieve_timestamp = relieve_row.get('f2_recdate')
            relieve_id = relieve_row.get('f2_id')
            action = relieve_row.get('f2_action') # Get action from dtfifo2

            if relieve_id is None: continue

            if relieve_timestamp and relieve_timestamp <= fj_timestamp:
                if relieve_id not in processed_relieve_ids:
                    # Only process 'Relieve Job' for Packaged Qty aggregation
                    if action == 'Relieve Job':
                        part_num = relieve_row.get('part_number', '')
                        part_desc = relieve_row.get('part_description', '')
                        quantity = safe_float(relieve_row.get('net_quantity'))

                        linked_fi_id = relieve_row.get('f2_fiid')
                        details = fi_id_to_details_map.get(linked_fi_id, {'lot_number': '', 'exp_date_raw': None})

                        raw_lot_num = details['lot_number']
                        stripped_lot_num = raw_lot_num.strip() if raw_lot_num else ''
                        raw_exp_date = details['exp_date_raw']
                        formatted_exp_date = _format_date(raw_exp_date)
                        final_lot_num_to_use = stripped_lot_num
                        final_exp_date_to_use = formatted_exp_date

                        if not stripped_lot_num:
                            found_existing_lot = False
                            for existing_key, existing_summary in job_data['aggregated_transactions'].items():
                                if existing_key[0] == part_num and existing_key[1] != 'N/A':
                                    final_lot_num_to_use = existing_key[1]
                                    final_exp_date_to_use = existing_key[2]
                                    found_existing_lot = True
                                    break
                            if not found_existing_lot:
                                final_lot_num_to_use = 'N/A'
                                final_exp_date_to_use = 'N/A'

                        normalized_lot_num = final_lot_num_to_use if final_lot_num_to_use else 'N/A'
                        normalized_exp_date = final_exp_date_to_use
                        agg_key = (part_num, normalized_lot_num, normalized_exp_date)

                        if not part_num: continue

                        if agg_key not in job_data['aggregated_transactions']:
                            job_data['aggregated_transactions'][agg_key] = {
                                'part_number': part_num, 'part_description': part_desc,
                                'lot_number': normalized_lot_num, 'exp_date': normalized_exp_date,
                                'Starting Lot Qty': 0.0, 'Ending Inventory': 0.0, 'Packaged Qty': 0.0,
                                'Yield Cost/Scrap': 0.0, 'Yield Loss': 0.0, '_UnRelieveJobQty': 0.0
                            }
                        if not job_data['aggregated_transactions'][agg_key].get('part_description') and part_desc:
                             job_data['aggregated_transactions'][agg_key]['part_description'] = part_desc

                        # Add the relieved quantity (from dtfifo2 'Relieve Job') to 'Packaged Qty'
                        job_data['aggregated_transactions'][agg_key]['Packaged Qty'] += quantity

                    # Mark ID as processed regardless of action type
                    processed_relieve_ids.add(relieve_id)

                if relieve_id in processed_relieve_ids:
                    relieve_pointer = i + 1

            elif relieve_timestamp and relieve_timestamp > fj_timestamp:
                 break

    # Calculate Yields after all transactions are aggregated
    for agg_key, summary in job_data['aggregated_transactions'].items():
        issued = summary.get('Starting Lot Qty', 0.0)
        relieve_from_dtfifo2 = summary.get('Packaged Qty', 0.0)
        unrelieve_from_dtfifo = summary.get('_UnRelieveJobQty', 0.0)
        net_packaged_qty = relieve_from_dtfifo2 - unrelieve_from_dtfifo
        summary['Packaged Qty'] = net_packaged_qty
        deissue = summary.get('Ending Inventory', 0.0)
        yield_cost = issued - net_packaged_qty - deissue
        summary['Yield Cost/Scrap'] = yield_cost
        summary['Yield Loss'] = (yield_cost / net_packaged_qty) * 100.0 if net_packaged_qty != 0 else 0.0

    # Finalize list for display
    job_data['aggregated_list'] = [
        summary for summary in job_data['aggregated_transactions'].values()
        if not summary.get('part_number', '').startswith('0800-')
           and summary.get('part_number', '') != job_data['part_number'] # Filter out FG
    ]
    job_data['aggregated_list'].sort(key=lambda x: (
        x.get('part_number', ''), x.get('lot_number', ''), x.get('exp_date', '')
    ))

    # Group by part number
    grouped_list = OrderedDict()
    for summary in job_data['aggregated_list']:
        part_num = summary.get('part_number', '')
        if part_num not in grouped_list:
            grouped_list[part_num] = { 'part_description': summary.get('part_description', ''), 'lots': [] }
        if '_UnRelieveJobQty' in summary: del summary['_UnRelieveJobQty']
        grouped_list[part_num]['lots'].append(summary)

    job_data['grouped_list'] = grouped_list
    del job_data['aggregated_transactions']

    return job_data
# ***** END HELPER FUNCTION *****


coc_report_bp = Blueprint('coc_report', __name__)

# --- Define the required access level for reports ---
REQUIRED_REPORT_ACCESS = lambda s: require_admin(s) or require_scheduling_admin(s) or require_scheduling_user(s)
# --- END MODIFICATION ---

@coc_report_bp.route('/coc', methods=['GET'])
@validate_session
def coc_report():
    if not require_login(session):
        return redirect(url_for('main.login'))
    # --- Use the broader access check ---
    if not REQUIRED_REPORT_ACCESS(session):
        flash('Report viewing privileges are required to view this report.', 'error')
        return redirect(url_for('main.dashboard'))
    # --- END MODIFICATION ---

    # --- MODIFICATION: Sanitize job number input ---
    job_number_input = request.args.get('job_number', '').strip()
    # Remove hyphens
    job_number_param = job_number_input.replace('-', '')
    # --- END MODIFICATION ---

    job_details = None
    error_message = None

    if job_number_param: # Use the cleaned version
        try:
            job_details = _get_single_job_details(job_number_param) # Pass cleaned version
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
        job_number=job_number_input, # Display original input in the form field
        job_details=job_details,
        error_message=error_message
    )

@coc_report_bp.route('/coc/pdf', methods=['GET'])
@validate_session
def coc_report_pdf():
    """
    Generates and serves a PDF version of the CoC report.
    """
    if not require_login(session):
        return redirect(url_for('main.login'))
    # --- Use the broader access check ---
    if not REQUIRED_REPORT_ACCESS(session):
        flash('Report viewing privileges are required to export reports.', 'error')
        return redirect(url_for('main.dashboard'))
    # --- END MODIFICATION ---

    # --- MODIFICATION: Sanitize job number input ---
    job_number_input = request.args.get('job_number', '').strip()
    job_number_param = job_number_input.replace('-', '') # Remove hyphens
    # --- END MODIFICATION ---

    if not job_number_param: # Check cleaned version
        flash('A Job Number is required to generate a PDF.', 'error')
        return redirect(url_for('.coc_report')) # Use relative redirect within blueprint

    try:
        # Get the same data as the web page, using cleaned job number
        job_details = _get_single_job_details(job_number_param)

        if not job_details or 'error' in job_details:
            error_message = job_details.get('error', 'Job not found')
            flash(f'Could not generate PDF: {error_message}', 'error')
            # Redirect using original input for consistency in URL
            return redirect(url_for('.coc_report', job_number=job_number_input))

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
        # Redirect using original input for consistency in URL
        return redirect(url_for('.coc_report', job_number=job_number_input))