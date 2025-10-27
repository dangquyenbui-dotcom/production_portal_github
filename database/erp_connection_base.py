# database/erp_connection_base.py
"""
Dedicated ERP Database Connection Base.
Handles the raw pyodbc connection logic.
ADDED: MARS_Connection=yes to connection string to prevent "busy with results" error.
"""
import pyodbc
import traceback
from config import Config

class ERPConnection:
    """Handles the raw connection to the ERP database."""
    def __init__(self):
        self.connection = None
        self._connection_string = None # Store the successful connection string

        # Prioritized list of potential drivers to try (braces removed)
        drivers_to_try = [
            Config.ERP_DB_DRIVER,  # First, try the one from .env
            'ODBC Driver 18 for SQL Server',
            'ODBC Driver 17 for SQL Server',
            'SQL Server Native Client 11.0',
            'SQL Server'
        ]

        # Remove duplicates while preserving order
        drivers = list(dict.fromkeys(d for d in drivers_to_try if d)) # Ensure no None or empty strings

        for driver in drivers:
            try:
                # The f-string correctly adds the necessary braces around the driver name
                # *** ADDED MARS_Connection=yes ***
                connection_string = (
                    f"DRIVER={{{driver}}};"
                    f"SERVER={Config.ERP_DB_SERVER},{Config.ERP_DB_PORT};"
                    f"DATABASE={Config.ERP_DB_NAME};"
                    f"UID={Config.ERP_DB_USERNAME};"
                    f"PWD={Config.ERP_DB_PASSWORD};"
                    f"TrustServerCertificate=yes;"
                    f"MARS_Connection=yes;" # <<< ADD THIS LINE
                    f"Connection Timeout={Config.ERP_DB_TIMEOUT};"
                )
                self.connection = pyodbc.connect(connection_string, autocommit=True)
                print(f"✅ [ERP_DB] Connection successful using driver: {driver} (MARS Enabled)")
                self._connection_string = connection_string  # Save the working string
                break  # Exit loop on successful connection
            except pyodbc.Error as e:
                # Only print error if it's not a driver-related issue that we expect to retry
                if 'driver' not in str(e).lower():
                    print(f"❌ [ERP_DB] Connection Error: {e}")
                print(f"ℹ️  [ERP_DB] Driver '{driver}' failed. Trying next...")
                continue # Try the next driver in the list

        if not self.connection:
            print(f"❌ [ERP_DB] FATAL: Connection failed. All attempted drivers were unsuccessful.")
            # Optionally, raise an exception here if a connection is critical
            # raise ConnectionError("Could not establish connection to ERP database.")


    def execute_query(self, sql, params=None):
        """Executes a SQL query and returns results as a list of dicts."""
        if not self.connection:
            print("❌ [ERP_DB] Cannot execute query, no active connection.")
            # Attempt to reconnect *once* if connection is None
            print("ℹ️ [ERP_DB] Attempting to reconnect...")
            self.__init__() # Re-run the connection logic
            if not self.connection:
                 print("❌ [ERP_DB] Reconnect failed. Aborting query.")
                 return []


        cursor = None # Initialize cursor to None
        try:
            # Check if connection is still valid by creating a cursor
            cursor = self.connection.cursor()

            cursor.execute(sql, params or [])
            if cursor.description:
                columns = [column[0] for column in cursor.description]
                # Use a try-except block for fetchall in case of disconnection during fetch
                try:
                    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                except pyodbc.Error as fetch_error:
                    print(f"❌ [ERP_DB] Error fetching results: {fetch_error}")
                    results = [] # Return empty list if fetch fails
                return results
            # Handle cases like INSERT/UPDATE/DELETE where description might be None
            # If autocommit=True, changes are already committed.
            return [] # Return empty list for non-SELECT or empty results
        except pyodbc.Error as e:
            print(f"❌ [ERP_DB] Query Failed: {e}")
            print(f"   SQL: {sql}")
            print(f"   Params: {params}")
            traceback.print_exc()
            # Attempt to reconnect might be added here, but be careful of loops.
            # Close potentially problematic connection
            self.close()
            return []
        except Exception as e:
            print(f"❌ [ERP_DB] Unexpected error during query execution: {e}")
            traceback.print_exc()
             # Close potentially problematic connection
            self.close()
            return []
        finally:
             if cursor:
                 try:
                     cursor.close()
                 except pyodbc.Error as cursor_close_error:
                     print(f"⚠️ [ERP_DB] Error closing cursor: {cursor_close_error}")


    def close(self):
        """Closes the database connection."""
        if self.connection:
            try:
                self.connection.close()
                self.connection = None
                print("ℹ️ [ERP_DB] Connection closed.")
            except pyodbc.Error as e:
                print(f"⚠️ [ERP_DB] Error closing connection: {e}")


# Singleton instance for the connection (optional, consider lifetime management)
_erp_connection_instance = None

def get_erp_db_connection():
    """
    Gets a shared instance of the ERP connection.
    Creates a new one if it doesn't exist or seems closed.
    """
    global _erp_connection_instance
    # Check if instance exists and if the connection seems valid
    connection_valid = False
    if _erp_connection_instance and _erp_connection_instance.connection:
        try:
            # More reliable check: attempt a simple query
            cursor = _erp_connection_instance.connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            connection_valid = True
        except pyodbc.Error:
             print("ℹ️ [ERP_DB] Existing connection test failed. Recreating instance.")
             _erp_connection_instance.close() # Close the potentially dead connection
             _erp_connection_instance = None # Force recreation

    if not connection_valid:
        print("ℹ️ [ERP_DB] Creating/Recreating ERPConnection instance.")
        _erp_connection_instance = ERPConnection()
        if _erp_connection_instance.connection is None:
             # Handle the case where the connection failed during initialization
             print("❌ [ERP_DB] Failed to create a valid ERPConnection.")
             return None # Or raise an exception

    return _erp_connection_instance