# routes/reports/coc.py
"""
Route for the Certificate of Compliance (CoC) Report.
FINAL VERSION: Uses refined logic for Packaged Qty calculation,
conditionally subtracting Un-Relieve based on timing.
ADDED: Shelf Life extraction for Finished Good.
ADDED: Batch Number extraction for Finished Good.
ADDED: Unit of Measure (UoM) extraction.
ADDED: Customer PO extraction.
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

# ***** FINAL HELPER FUNCTION for CoC Report *****
def _get_single_job_details(job_number_str):
    """
    Fetches and processes data for CoC report.
    Refined Logic: 'Packaged Qty' conditionally subtracts Un-Relieve (dtfifo) based on timing.
                   Yield calculation uses the final Packaged Qty.
    ADDED: Extracts Shelf Life dates, Batch Numbers, UoM, and Customer PO.
    """
    if not job_number_str:
        return None

    erp_service = get_erp_service()
    raw_data = erp_service.get_coc_report_data(job_number_str)

    if not raw_data or not raw_data.get("header"):
        return {'error': f"Job '{job_number_str}' not found in the ERP system."}

    header = raw_data["header"]
    fifo_details = raw_data.get("fifo_details", [])
    relieve_details = raw_data.get("relieve_details", []) # dtfifo2 data

    job_data = {
        'job_number': str(header['jo_jobnum']),
        'part_number': header.get('part_number', ''),
        'part_description': header.get('part_description', ''),
        'customer_name': header.get('customer_name', 'N/A'),
        'sales_order': str(header.get('sales_order_number', '')) if header.get('sales_order_number') else '',
        'customer_po': header.get('customer_po', 'N/A'), # <<< ADDED: Customer PO
        'required_qty': safe_float(header.get('required_quantity')),
        'completed_qty': 0.0,
        'unit_of_measure': header.get('unit_of_measure', 'N/A'),
        'aggregated_transactions': {}, # Intermediate storage
        'shelf_life_dates': set(),
        'batch_numbers': set()
    }

    finished_good_part = job_data['part_number']

    finish_job_entries = [] # Store {'timestamp': dt, 'quantity': float}
    fi_id_to_details_map = { row.get('fi_id'): {'lot_number': row.get('lot_number', ''), 'exp_date_raw': row.get('fi_expires')} for row in fifo_details if row.get('fi_id') }

    # --- Step 1: FIFO Processing - Accumulate initial values ---
    for row in fifo_details:
        action = row.get('fi_action')
        timestamp = row.get('fi_recdate') # Keep as datetime
        quantity = safe_float(row.get('fi_quant'))
        fi_id = row.get('fi_id')
        part_num = row.get('part_number', '')
        raw_exp_date = row.get('fi_expires')
        batch_num = row.get('lot_number', '')
        uom = row.get('unit_of_measure', '')

        # Accumulate FG 'Finish Job' qty, store entry, collect expiration dates and batch numbers
        if action == 'Finish Job' and timestamp and part_num == finished_good_part:
            finish_job_entries.append({'timestamp': timestamp, 'quantity': quantity})
            job_data['completed_qty'] += quantity
            # --- Collect formatted shelf life date ---
            formatted_exp = _format_date(raw_exp_date)
            if formatted_exp != 'N/A':
                job_data['shelf_life_dates'].add(formatted_exp)
            # --- Collect batch number ---
            if batch_num and batch_num.strip():
                job_data['batch_numbers'].add(batch_num.strip())

        # Aggregate component transactions
        elif part_num != finished_good_part: # Ignore FG for aggregation table
            part_desc = row.get('part_description', '')
            raw_lot_num = row.get('lot_number', '')
            stripped_lot_num = raw_lot_num.strip() if raw_lot_num else ''
            normalized_lot_num = stripped_lot_num if stripped_lot_num else 'N/A'
            formatted_exp_date = _format_date(raw_exp_date)
            normalized_exp_date = formatted_exp_date
            agg_key = (part_num, normalized_lot_num, normalized_exp_date)

            if not part_num: continue

            # Initialize aggregation dict if key doesn't exist
            if agg_key not in job_data['aggregated_transactions']:
                job_data['aggregated_transactions'][agg_key] = {
                    'part_number': part_num, 'part_description': part_desc,
                    'lot_number': normalized_lot_num, 'exp_date': normalized_exp_date,
                    'unit_of_measure': uom or 'N/A',
                    'Starting Lot Qty': 0.0, 'Ending Inventory': 0.0, 'Gross Packaged Qty': 0.0,
                    'Yield Cost/Scrap': 0.0, 'Yield Loss': 0.0,
                    '_UnRelieveTransactions': []
                }
            # Update description if it was missing initially
            if not job_data['aggregated_transactions'][agg_key].get('part_description') and part_desc:
                 job_data['aggregated_transactions'][agg_key]['part_description'] = part_desc
            # Update UoM if it was missing initially
            if job_data['aggregated_transactions'][agg_key].get('unit_of_measure') == 'N/A' and uom:
                 job_data['aggregated_transactions'][agg_key]['unit_of_measure'] = uom

            # Aggregate quantities based on action
            if action == 'Issued inventory':
                job_data['aggregated_transactions'][agg_key]['Starting Lot Qty'] += quantity
            elif action == 'De-issue':
                job_data['aggregated_transactions'][agg_key]['Ending Inventory'] += quantity
            elif action == 'Un-relieve Job':
                if timestamp:
                    job_data['aggregated_transactions'][agg_key]['_UnRelieveTransactions'].append({'qty': quantity, 'timestamp': timestamp})

    # --- Step 2: DTFIFO2 'Un-finish Job' Processing ---
    for relieve_row in relieve_details:
        action = relieve_row.get('f2_action')
        part_num = relieve_row.get('part_number', '')
        quantity_adjustment = safe_float(relieve_row.get('net_quantity'))
        if action == 'Un-finish Job' and part_num == finished_good_part:
             job_data['completed_qty'] -= quantity_adjustment

    # Sort 'Finish Job' entries and find the last one's timestamp
    finish_job_entries.sort(key=lambda x: x['timestamp'])
    last_finish_job_timestamp = finish_job_entries[-1]['timestamp'] if finish_job_entries else None

    # --- Step 3: DTFIFO2 'Relieve Job' Aggregation ---
    relieve_pointer = 0
    processed_relieve_ids = set()
    for fj_entry in finish_job_entries:
        fj_timestamp = fj_entry['timestamp']

        for i in range(relieve_pointer, len(relieve_details)):
            relieve_row = relieve_details[i]
            relieve_timestamp = relieve_row.get('f2_recdate')
            relieve_id = relieve_row.get('f2_id')
            action = relieve_row.get('f2_action')

            if relieve_id is None: continue

            if relieve_timestamp and relieve_timestamp <= fj_timestamp:
                if relieve_id not in processed_relieve_ids:
                    if action == 'Relieve Job' and relieve_row.get('part_number', '') != finished_good_part:
                        part_num = relieve_row.get('part_number', '')
                        part_desc = relieve_row.get('part_description', '')
                        quantity = safe_float(relieve_row.get('net_quantity'))
                        uom = relieve_row.get('unit_of_measure', '')
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
                                'unit_of_measure': uom or 'N/A',
                                'Starting Lot Qty': 0.0, 'Ending Inventory': 0.0, 'Gross Packaged Qty': 0.0,
                                'Yield Cost/Scrap': 0.0, 'Yield Loss': 0.0, '_UnRelieveTransactions': []
                            }
                        if not job_data['aggregated_transactions'][agg_key].get('part_description') and part_desc:
                             job_data['aggregated_transactions'][agg_key]['part_description'] = part_desc
                        if job_data['aggregated_transactions'][agg_key].get('unit_of_measure') == 'N/A' and uom:
                             job_data['aggregated_transactions'][agg_key]['unit_of_measure'] = uom

                        job_data['aggregated_transactions'][agg_key]['Gross Packaged Qty'] += quantity

                    processed_relieve_ids.add(relieve_id)

                if relieve_id in processed_relieve_ids:
                    relieve_pointer = i + 1

            elif relieve_timestamp and relieve_timestamp > fj_timestamp:
                 break

    # --- Step 4: Final Yield Calculation with Conditional Netting ---
    for agg_key, summary in job_data['aggregated_transactions'].items():
        issued = summary.get('Starting Lot Qty', 0.0)
        gross_packaged_qty = summary.get('Gross Packaged Qty', 0.0)
        unrelieve_transactions = summary.get('_UnRelieveTransactions', [])
        deissue = summary.get('Ending Inventory', 0.0)

        net_unrelieve_to_subtract = 0.0
        for unrelieve in unrelieve_transactions:
            if last_finish_job_timestamp and unrelieve['timestamp'] <= last_finish_job_timestamp:
                net_unrelieve_to_subtract += unrelieve['qty']

        final_packaged_qty = gross_packaged_qty - net_unrelieve_to_subtract
        summary['Packaged Qty'] = final_packaged_qty

        yield_cost = issued - final_packaged_qty - deissue
        summary['Yield Cost/Scrap'] = yield_cost

        summary['Yield Loss'] = (yield_cost / final_packaged_qty) * 100.0 if final_packaged_qty != 0 else 0.0

    # --- Finalize list, group for display, format shelf life, and format batch numbers ---
    job_data['aggregated_list'] = [
        summary for summary in job_data['aggregated_transactions'].values()
        if not summary.get('part_number', '').startswith('0800-')
           and summary.get('part_number', '') != job_data['part_number']
    ]
    job_data['aggregated_list'].sort(key=lambda x: (
        x.get('part_number', ''), x.get('lot_number', ''), x.get('exp_date', '')
    ))

    grouped_list = OrderedDict()
    for summary in job_data['aggregated_list']:
        part_num = summary.get('part_number', '')
        if part_num not in grouped_list:
            grouped_list[part_num] = {
                'part_description': summary.get('part_description', ''),
                'unit_of_measure': summary.get('unit_of_measure', 'N/A'),
                'lots': []
            }
        if grouped_list[part_num]['unit_of_measure'] == 'N/A' and summary.get('unit_of_measure') != 'N/A':
            grouped_list[part_num]['unit_of_measure'] = summary.get('unit_of_measure')

        if '_UnRelieveTransactions' in summary: del summary['_UnRelieveTransactions']
        if 'Gross Packaged Qty' in summary: del summary['Gross Packaged Qty']
        grouped_list[part_num]['lots'].append(summary)

    job_data['grouped_list'] = grouped_list
    del job_data['aggregated_transactions']

    # --- Format shelf life dates for display ---
    sorted_dates = sorted(list(job_data['shelf_life_dates']))
    job_data['shelf_life_display'] = ', '.join(sorted_dates) if sorted_dates else 'N/A'
    del job_data['shelf_life_dates']

    # --- Format batch numbers for display ---
    sorted_batches = sorted(list(job_data['batch_numbers']))
    job_data['batch_number_display'] = '<br>'.join(sorted_batches) if sorted_batches else 'N/A'
    del job_data['batch_numbers']

    return job_data
# ***** END FINAL HELPER FUNCTION *****


coc_report_bp = Blueprint('coc_report', __name__)

# --- Define the required access level for reports ---
REQUIRED_REPORT_ACCESS = lambda s: require_admin(s) or require_scheduling_admin(s) or require_scheduling_user(s)
# --- END MODIFICATION ---

@coc_report_bp.route('/coc', methods=['GET'])
@validate_session
def coc_report():
    if not require_login(session):
        return redirect(url_for('main.login'))
    if not REQUIRED_REPORT_ACCESS(session):
        flash('Report viewing privileges are required to view this report.', 'error')
        return redirect(url_for('main.dashboard'))

    job_number_input = request.args.get('job_number', '').strip()
    job_number_param = job_number_input.replace('-', '') # Remove hyphens

    job_details = None
    error_message = None

    if job_number_param:
        try:
            # Use the final refined logic as the default
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
        job_number=job_number_input, # Display original input
        job_details=job_details,
        error_message=error_message,
        test_mode_active=False # No longer needed
    )

@coc_report_bp.route('/coc/pdf', methods=['GET'])
@validate_session
def coc_report_pdf():
    """
    Generates and serves a PDF version of the CoC report using the final logic.
    """
    if not require_login(session):
        return redirect(url_for('main.login'))
    if not REQUIRED_REPORT_ACCESS(session):
        flash('Report viewing privileges are required to export reports.', 'error')
        return redirect(url_for('main.dashboard'))

    job_number_input = request.args.get('job_number', '').strip()
    job_number_param = job_number_input.replace('-', '')

    if not job_number_param:
        flash('A Job Number is required to generate a PDF.', 'error')
        return redirect(url_for('.coc_report'))

    try:
        # Use the final refined logic
        job_details = _get_single_job_details(job_number_param)

        if not job_details or 'error' in job_details:
            error_message = job_details.get('error', 'Job not found')
            flash(f'Could not generate PDF: {error_message}', 'error')
            return redirect(url_for('.coc_report', job_number=job_number_input))

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
        return redirect(url_for('.coc_report', job_number=job_number_input))