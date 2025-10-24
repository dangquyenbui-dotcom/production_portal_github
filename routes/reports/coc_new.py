# routes/reports/coc.py
"""
Route for the Certificate of Compliance (CoC) Report.
<<< FINAL CORRECTED LOGIC based on user confirmation and file structure:
    - 'Un-relieve Job' is ONLY in dtfifo (fi_quant).
    - 'Relieve Job' is ONLY in dtfifo2 (net_quantity = f2_oldquan - f2_newquan > 0).
    - Packaged Qty = SUM(dtfifo2.RelieveJob.net_quantity) - SUM(dtfifo.UnRelieveJob.fi_quant)
>>>
"""
from flask import (
    Blueprint, render_template, redirect, url_for, session, request, flash, send_file,
    current_app
)
from auth import (
    require_login, require_admin, require_scheduling_admin, require_scheduling_user
)
from routes.main import validate_session
from database import get_erp_service
from datetime import datetime, timedelta
import traceback
from collections import OrderedDict
import io
from utils.pdf_generator import generate_coc_pdf

coc_report_bp = Blueprint('coc_report', __name__)

# --- Define the required access level for reports ---
REQUIRED_REPORT_ACCESS = lambda s: require_admin(s) or require_scheduling_admin(s) or require_scheduling_user(s)
# --- END MODIFICATION ---

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

    print(f"--- CoC Report DEBUG: Starting job {job_number_str} ---") # DEBUG LOG

    erp_service = get_erp_service()
    raw_data = erp_service.get_coc_report_data(job_number_str)

    if not raw_data or not raw_data.get("header"):
        print(f"--- CoC Report DEBUG: Job header not found for {job_number_str} ---") # DEBUG LOG
        return {'error': f"Job '{job_number_str}' not found in the ERP system."}

    header = raw_data["header"]
    fifo_details = raw_data.get("fifo_details", [])      # Contains 'Un-relieve Job'
    relieve_details = raw_data.get("relieve_details", []) # Contains 'Relieve Job', 'Un-finish Job'

    print(f"--- CoC Report DEBUG: Fetched {len(fifo_details)} FIFO details and {len(relieve_details)} dtfifo2 details ---") # DEBUG LOG

    job_data = {
        'job_number': str(header['jo_jobnum']),
        'part_number': header.get('part_number', ''),
        'part_description': header.get('part_description', ''),
        'customer_name': header.get('customer_name', 'N/A'),
        'sales_order': str(header.get('sales_order_number', '')) if header.get('sales_order_number') else '',
        'required_qty': safe_float(header.get('required_quantity')),
        'completed_qty': 0.0, # Will be adjusted by Un-finish Job
        'aggregated_transactions': {} # Use standard dict
    }

    # Map fi_id to lot and formatted expiration date for relieve linking (Needed for dtfifo2)
    fi_id_to_details_map = {
        row.get('fi_id'): {
            'lot_number': row.get('lot_number', ''), # Already normalized to '' if NULL by query
            'exp_date_raw': row.get('fi_expires') # Store raw date
        }
        for row in fifo_details if row.get('fi_id')
    }

    # --- Step 1: Process dtfifo for Issues, De-issues, initial Completed Qty, AND Un-relieve Job ---
    for row in fifo_details:
        action = row.get('fi_action')
        quantity = safe_float(row.get('fi_quant')) # Use fi_quant from dtfifo
        fi_id = row.get('fi_id')

        # Sum initial Completed Qty from dtfifo 'Finish Job'
        if action == 'Finish Job':
            job_data['completed_qty'] += quantity
            continue # Don't aggregate FG in component list

        # Aggregate Issue/De-issue/Un-relieve
        if action in ('Issued inventory', 'De-issue', 'Un-relieve Job'):
            part_num = row.get('part_number', '')
            part_desc = row.get('part_description', '')

            # Lot/Exp Date Normalization
            raw_lot_num = row.get('lot_number', '')
            stripped_lot_num = raw_lot_num.strip() if raw_lot_num else ''
            normalized_lot_num = stripped_lot_num if stripped_lot_num else 'N/A'
            raw_exp_date = row.get('fi_expires')
            formatted_exp_date = _format_date(raw_exp_date)
            normalized_exp_date = formatted_exp_date
            agg_key = (part_num, normalized_lot_num, normalized_exp_date)

            if not part_num: continue

            # Initialize aggregation dict if needed
            if agg_key not in job_data['aggregated_transactions']:
                job_data['aggregated_transactions'][agg_key] = {
                    'part_number': part_num,
                    'part_description': part_desc,
                    'lot_number': normalized_lot_num,
                    'exp_date': normalized_exp_date,
                    'Starting Lot Qty': 0.0,
                    'Ending Inventory': 0.0,
                    'Packaged Qty': 0.0, # Initialize Net packaged qty
                    'Yield Cost/Scrap': 0.0,
                    'Yield Loss': 0.0
                }
            # Update description if missing
            if not job_data['aggregated_transactions'][agg_key].get('part_description') and part_desc:
                 job_data['aggregated_transactions'][agg_key]['part_description'] = part_desc

            # Apply action
            if action == 'Issued inventory':
                job_data['aggregated_transactions'][agg_key]['Starting Lot Qty'] += quantity
            elif action == 'De-issue':
                job_data['aggregated_transactions'][agg_key]['Ending Inventory'] += quantity
            elif action == 'Un-relieve Job':
                # <<< Subtract fi_quant for Un-relieve Job from dtfifo >>>
                current_pkg_qty = job_data['aggregated_transactions'][agg_key]['Packaged Qty']
                job_data['aggregated_transactions'][agg_key]['Packaged Qty'] -= quantity
                new_pkg_qty = job_data['aggregated_transactions'][agg_key]['Packaged Qty']
                if part_num == '5330-020' and job_number_str == '202505169': # DEBUG LOG
                    print(f"--- CoC Report DEBUG [DTFIFO UN-RELIEVE]: Key={agg_key}, fi_id={fi_id}, Action='{action}', fi_quant={quantity}, OldPkgQty={current_pkg_qty}, NewPkgQty={new_pkg_qty} ---")


    # --- Step 2: Process dtfifo2 for Relieve Job and Un-finish Job ---
    processed_f2_ids = set()
    for row in relieve_details:
        f2_id = row.get('f2_id')
        action = row.get('f2_action')
        # Use SIGNED net_quantity from the query (f2_oldquan - f2_newquan)
        signed_quantity = safe_float(row.get('net_quantity'))

        if f2_id is None or action is None: continue
        if f2_id in processed_f2_ids: continue

        # Handle Un-finish Job
        if action == 'Un-finish Job':
            unfinish_qty_abs = abs(signed_quantity) # Use abs as sign might be inconsistent
            job_data['completed_qty'] -= unfinish_qty_abs
            processed_f2_ids.add(f2_id)
            if job_number_str == '202505169': # DEBUG LOG
                print(f"--- CoC Report DEBUG [UN-FINISH]: f2_id={f2_id}, Qty Subtracted={unfinish_qty_abs}. New completed_qty = {job_data['completed_qty']} ---")
            continue

        # Handle Relieve Job (ONLY action left affecting components in dtfifo2)
        if action == 'Relieve Job':
            part_num = row.get('part_number', '')
            part_desc = row.get('part_description', '') # Get description from dtfifo2 row as fallback
            linked_fi_id = row.get('f2_fiid')
            details = fi_id_to_details_map.get(linked_fi_id, {'lot_number': '', 'exp_date_raw': None})

            # Lot/Exp Date Normalization & Override Logic (same as before)
            raw_lot_num = details['lot_number']
            stripped_lot_num = raw_lot_num.strip() if raw_lot_num else ''
            raw_exp_date = details['exp_date_raw']
            formatted_exp_date = _format_date(raw_exp_date)
            final_lot_num_to_use = stripped_lot_num
            final_exp_date_to_use = formatted_exp_date
            if not stripped_lot_num:
                found_existing_lot = False
                for existing_key in job_data['aggregated_transactions']:
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

            # Initialize aggregation dict if needed (e.g., if only Relieve exists)
            if agg_key not in job_data['aggregated_transactions']:
                job_data['aggregated_transactions'][agg_key] = {
                    'part_number': part_num,
                    'part_description': part_desc, # Use description from dtfifo2 row
                    'lot_number': normalized_lot_num,
                    'exp_date': normalized_exp_date,
                    'Starting Lot Qty': 0.0,
                    'Ending Inventory': 0.0,
                    'Packaged Qty': 0.0, # Initialize Net packaged qty
                    'Yield Cost/Scrap': 0.0,
                    'Yield Loss': 0.0
                }
                if part_num == '5330-020' and job_number_str == '202505169': # DEBUG LOG
                    print(f"--- CoC Report DEBUG [NEW AGG KEY from dtfifo2 RELIEVE]: Key={agg_key} ---")

            # <<< Add the POSITIVE net_quantity for Relieve Job from dtfifo2 >>>
            current_pkg_qty = job_data['aggregated_transactions'][agg_key]['Packaged Qty']
            # net_quantity is positive for Relieve Job
            job_data['aggregated_transactions'][agg_key]['Packaged Qty'] += signed_quantity
            new_pkg_qty = job_data['aggregated_transactions'][agg_key]['Packaged Qty']
            if part_num == '5330-020' and job_number_str == '202505169': # DEBUG LOG
                print(f"--- CoC Report DEBUG [DTFIFO2 RELIEVE]: Key={agg_key}, f2_id={f2_id}, Action='{action}', SignedQty={signed_quantity}, OldPkgQty={current_pkg_qty}, NewPkgQty={new_pkg_qty} ---")

            processed_f2_ids.add(f2_id)


    # --- Step 3: Calculate Yields ---
    for agg_key, summary in job_data['aggregated_transactions'].items():
        issued = summary.get('Starting Lot Qty', 0.0)
        net_packaged_qty = summary.get('Packaged Qty', 0.0) # This IS the final net packaged qty
        deissue = summary.get('Ending Inventory', 0.0)
        yield_cost = issued - net_packaged_qty - deissue # Use net quantity
        summary['Yield Cost/Scrap'] = yield_cost
        # Prevent division by zero
        summary['Yield Loss'] = (yield_cost / net_packaged_qty) * 100.0 if net_packaged_qty != 0 else 0.0

        # <<< --- DEBUG LOG --- >>>
        if summary.get('part_number') == '5330-020' and job_number_str == '202505169':
            print(f"--- CoC Report DEBUG [AGGREGATED FINAL]: Key={agg_key}, Lot={summary.get('lot_number')}, Issued={issued}, Net_Packaged_Qty={net_packaged_qty}, Deissue={deissue}, YieldCost={yield_cost}, YieldLoss={summary['Yield Loss']}% ---")
        # <<< --- END DEBUG LOG --- >>>

    # Create the final list for display, filtering out unwanted parts (unchanged)
    job_data['aggregated_list'] = [
        summary for summary in job_data['aggregated_transactions'].values()
        if not summary.get('part_number', '').startswith('0800-')
           and summary.get('part_number', '') != job_data['part_number']
    ]
    # Sort the final list (unchanged)
    job_data['aggregated_list'].sort(key=lambda x: (
        x.get('part_number', ''),
        x.get('lot_number', ''),
        x.get('exp_date', '')
    ))

    # Group by part number for display (unchanged)
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

    # Remove the intermediate structure (unchanged)
    del job_data['aggregated_transactions']

    print(f"--- CoC Report DEBUG: Finished processing job {job_number_str}. Final Completed Qty: {job_data['completed_qty']} ---") # DEBUG LOG
    return job_data
# ***** END HELPER FUNCTION *****


@coc_report_bp.route('/coc', methods=['GET'])
@validate_session
def coc_report():
    if not require_login(session):
        return redirect(url_for('main.login'))
    if not REQUIRED_REPORT_ACCESS(session):
        flash('Report viewing privileges are required to view this report.', 'error')
        return redirect(url_for('main.dashboard'))

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

@coc_report_bp.route('/coc/pdf', methods=['GET'])
@validate_session
def coc_report_pdf():
    if not require_login(session):
        return redirect(url_for('main.login'))
    if not REQUIRED_REPORT_ACCESS(session):
        flash('Report viewing privileges are required to export reports.', 'error')
        return redirect(url_for('main.dashboard'))

    job_number_param = request.args.get('job_number', '').strip()
    if not job_number_param:
        flash('A Job Number is required to generate a PDF.', 'error')
        return redirect(url_for('.coc_report'))

    try:
        job_details = _get_single_job_details(job_number_param)
        if not job_details or 'error' in job_details:
            error_message = job_details.get('error', 'Job not found')
            flash(f'Could not generate PDF: {error_message}', 'error')
            return redirect(url_for('.coc_report', job_number=job_number_param))

        app_root_path = current_app.root_path
        pdf_buffer, filename = generate_coc_pdf(job_details, app_root_path)

        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
    except Exception as e:
        flash(f'An error occurred while generating the PDF: {e}', 'error')
        traceback.print_exc()
        return redirect(url_for('.coc_report', job_number=job_number_param))