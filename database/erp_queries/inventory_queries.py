# database/erp_queries/inventory_queries.py
"""
ERP Queries related to Inventory.
MODIFIED: Added Customer Name to get_detailed_fg_inventory query.
MODIFIED: Added BU to get_detailed_fg_inventory query.
"""
from database.erp_connection_base import get_erp_db_connection
from datetime import datetime # Ensure datetime is imported if used for type hints, etc.

class InventoryQueries:
    """Contains ERP query methods specific to Inventory."""

    def get_raw_material_inventory(self):
        """
        Retrieves raw material inventory categorized by status. Excludes Finished Goods.
        """
        # ... (no changes to this method) ...
        db = get_erp_db_connection()
        if not db: return []
        sql = """
            SELECT
                p.pr_codenum AS PartNumber,
                SUM(CASE WHEN f.fi_type NOT IN ('quarantine', 'job', 'staging') AND (f.fi_qc IS NULL OR f.fi_qc <> 'Pending') THEN f.fi_balance ELSE 0 END) AS on_hand_approved,
                SUM(CASE WHEN f.fi_qc = 'Pending' THEN f.fi_balance ELSE 0 END) AS on_hand_pending_qc,
                SUM(CASE WHEN f.fi_type = 'quarantine' THEN f.fi_balance ELSE 0 END) AS on_hand_quarantine,
                SUM(CASE WHEN f.fi_type = 'job' AND f.fi_action = 'Issued inventory' THEN f.fi_balance ELSE 0 END) AS issued_to_job,
                SUM(CASE WHEN f.fi_type = 'staging' THEN f.fi_balance ELSE 0 END) AS staged
            FROM dtfifo f
            JOIN dmprod p ON f.fi_prid = p.pr_id
            WHERE f.fi_balance > 0 AND p.pr_codenum NOT LIKE 'T%'
            GROUP BY p.pr_codenum;
        """
        return db.execute_query(sql)


    def get_on_hand_inventory(self):
        """
        Retrieves Finished Goods inventory (parts starting with 'T') grouped by part number.
        Splits quantities into 'approved' and 'pending_qc'.
        """
        # ... (no changes to this method) ...
        db = get_erp_db_connection()
        if not db: return []
        sql = """
            SELECT
                p.pr_codenum AS PartNumber,
                SUM(CASE WHEN (f.fi_qc IS NULL OR f.fi_qc <> 'Pending') THEN f.fi_balance ELSE 0 END) AS on_hand_approved,
                SUM(CASE WHEN f.fi_qc = 'Pending' THEN f.fi_balance ELSE 0 END) AS on_hand_pending_qc,
                SUM(f.fi_balance) AS TotalOnHand
            FROM dtfifo f
            JOIN dmprod p ON f.fi_prid = p.pr_id
            JOIN dmware w ON f.fi_waid = w.wa_id
            WHERE f.fi_balance > 0 AND p.pr_codenum LIKE 'T%' AND w.wa_name IN ('DUARTE', 'IRWINDALE')
            GROUP BY p.pr_codenum;
        """
        return db.execute_query(sql)


    # --- MODIFIED METHOD ---
    def get_detailed_fg_inventory(self, start_date=None, end_date=None):
        """
        Retrieves detailed Finished Goods inventory data (Part, Lot, Date, Qty, Warehouse, Value, Customer, BU)
        optionally filtered by lot date range. Dates should be in 'YYYY-MM-DD' format.
        """
        db = get_erp_db_connection()
        if not db: return []

        sql = """
            SELECT
                p.pr_codenum AS PartNumber,
                p.pr_descrip AS PartDescription,
                -- *** ADDED Customer Name ***
                ISNULL(cust.p1_name, 'N/A') AS CustomerName,
                -- *** ADDED BU ***
                CASE WHEN ca.ca_name = 'Stick Pack' THEN 'SP' ELSE 'BPS' END AS BU,
                f.fi_lotnum AS SystemLot,
                f.fi_userlot AS UserLot,
                f.fi_lotdate AS LotDate,
                f.fi_expires AS ExpirationDate,
                f.fi_balance AS OnHandQuantity,
                w.wa_name AS Warehouse,
                p.pr_lispric AS ListPrice,
                f.fi_balance * p.pr_lispric AS InventoryValue,
                CASE WHEN f.fi_qc = 'Pending' THEN 'Pending QC' ELSE 'Approved' END AS QCStatus
            FROM dtfifo f
            JOIN dmprod p ON f.fi_prid = p.pr_id
            JOIN dmware w ON f.fi_waid = w.wa_id
            -- *** ADDED Join for Customer ***
            LEFT JOIN dmpr1 cust ON p.pr_user5 = cust.p1_id
            -- *** ADDED Join for BU ***
            LEFT JOIN dmcats ca ON p.pr_caid = ca.ca_id
            WHERE f.fi_balance > 0
              AND p.pr_codenum LIKE 'T%'
              AND w.wa_name IN ('DUARTE', 'IRWINDALE')
        """
        params = []
        if start_date and end_date:
            sql += " AND f.fi_lotdate >= ? AND f.fi_lotdate < ? " # Use >= start and < end for bucket logic
            params.extend([start_date, end_date])
        elif start_date: # Only start date means >= start_date (for the 'recent' bucket)
            sql += " AND f.fi_lotdate >= ? "
            params.append(start_date)
        elif end_date: # Only end date means < end_date (for the 'prior' bucket)
             sql += " AND f.fi_lotdate < ? "
             params.append(end_date)
        # If neither date is provided, it returns all FG inventory.

        sql += " ORDER BY p.pr_codenum, f.fi_lotdate, f.fi_lotnum;"

        results = db.execute_query(sql, params)

        # Convert datetime objects to strings
        if results:
            for row in results:
                if isinstance(row.get('LotDate'), datetime):
                    row['LotDate'] = row['LotDate'].strftime('%Y-%m-%d')
                if isinstance(row.get('ExpirationDate'), datetime):
                    # Handle potential default/invalid dates from ERP
                    if row['ExpirationDate'].year <= 1900:
                         row['ExpirationDate'] = 'N/A'
                    else:
                         row['ExpirationDate'] = row['ExpirationDate'].strftime('%Y-%m-%d')
                elif row.get('ExpirationDate') is None:
                     row['ExpirationDate'] = 'N/A' # Explicitly set None to 'N/A'


        return results
    # --- END MODIFIED METHOD ---