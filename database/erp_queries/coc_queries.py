# database/erp_queries/coc_queries.py
"""
ERP Queries specifically for the Certificate of Compliance (CoC) Report.
Fetches header and transaction data for any job number, regardless of status.
MODIFIED: get_job_relieve_data now includes 'Un-finish Job' actions.
ADDED: Unit of Measure (UoM) to all queries.
ADDED: Customer PO (to_billpo) to header query.
"""
from database.erp_connection_base import get_erp_db_connection

class CoCQueries:
    """Contains ERP query methods specific to the CoC Report."""

    def get_job_header_by_number(self, job_number):
        """
        Retrieves primary header info for a SINGLE job number, regardless of status or type.
        Includes UoM for the finished good and Customer PO.
        """
        db = get_erp_db_connection()
        if not db: return None # Return None if connection fails

        sql = """
            WITH PrimaryLine AS (
                SELECT TOP 1 -- Get only the first line for header info
                    lj.lj_jobnum,
                    lj.lj_ordnum,
                    lj.lj_quant AS required_quantity,
                    lj.lj_prid, -- Product ID from the job line
                    lj.lj_linenum
                FROM dtljob lj
                WHERE lj.lj_jobnum = ?
                ORDER BY lj.lj_linenum ASC -- Ensure consistency
            )
            SELECT
                j.jo_jobnum,
                j.jo_closed, -- Include closed status
                j.jo_type, -- Include job type
                pl.lj_ordnum AS sales_order_number,
                so_header.to_billpo AS customer_po, -- <<< ADDED Customer PO
                pl.required_quantity,
                p.pr_codenum AS part_number,
                p.pr_descrip AS part_description,
                ISNULL(cust.p1_name, 'N/A') AS customer_name,
                ISNULL(u.un_name, '') AS unit_of_measure
            FROM dtjob j
            LEFT JOIN PrimaryLine pl ON j.jo_jobnum = pl.lj_jobnum
            LEFT JOIN dmprod p ON pl.lj_prid = p.pr_id
            LEFT JOIN dmpr1 cust ON p.pr_user5 = cust.p1_id
            LEFT JOIN dmunit u ON p.pr_unid = u.un_id
            LEFT JOIN dttord so_header ON pl.lj_ordnum = so_header.to_ordnum -- <<< ADDED JOIN to get PO
            WHERE j.jo_jobnum = ?; -- Filter only by job number
        """
        # Pass job number twice for the two WHERE clauses
        params = [job_number, job_number]
        results = db.execute_query(sql, params)
        return results[0] if results else None # Return the first result or None

    def get_job_transaction_details(self, job_number):
        """
        Retrieves TRANSACTION details (dtfifo) for a specific job number.
        Includes fi_recdate, fi_userlot, fi_id, fi_expires, and UoM.
        """
        if not job_number: return []
        db = get_erp_db_connection()
        if not db: return []

        prefixed_job_number = f'JJ-{job_number}'

        sql = """
            SELECT
                f.fi_id,
                f.fi_postref,
                f.fi_action,
                f.fi_quant,
                f.fi_prid,
                f.fi_recdate,
                ISNULL(f.fi_userlot, '') AS lot_number,
                f.fi_expires,
                p_fifo.pr_codenum AS part_number,
                p_fifo.pr_descrip AS part_description,
                ISNULL(u.un_name, '') AS unit_of_measure
            FROM dtfifo f
            LEFT JOIN dmprod p_fifo ON f.fi_prid = p_fifo.pr_id
            LEFT JOIN dmunit u ON p_fifo.pr_unid = u.un_id
            WHERE f.fi_postref = ?
            ORDER BY f.fi_recdate ASC; -- Order by date to process chronologically
        """
        params = [prefixed_job_number]
        return db.execute_query(sql, params)

    def get_job_relieve_data(self, job_number):
        """
        Retrieves relieve job data (dtfifo2) for a specific job number.
        Includes f2_recdate, f2_fiid, 'Un-finish Job' actions, and UoM.
        """
        if not job_number: return []
        db = get_erp_db_connection()
        if not db: return []

        prefixed_job_number = f'JJ-{job_number}'

        sql = """
            SELECT
                f2.f2_id,
                f2.f2_postref,
                f2.f2_action,
                f2.f2_prid,
                f2.f2_recdate,
                f2.f2_fiid,
                (f2.f2_oldquan - f2.f2_newquan) AS net_quantity,
                p.pr_codenum AS part_number,
                p.pr_descrip AS part_description,
                ISNULL(u.un_name, '') AS unit_of_measure
            FROM dtfifo2 f2
            LEFT JOIN dmprod p ON f2.f2_prid = p.pr_id
            LEFT JOIN dmunit u ON p.pr_unid = u.un_id
            WHERE f2.f2_postref = ?
            AND f2.f2_action IN ('Relieve Job', 'Un-finish Job')
            ORDER BY f2.f2_recdate ASC; -- Order by date to process chronologically
        """
        params = [prefixed_job_number]
        return db.execute_query(sql, params)