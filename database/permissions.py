# database/permissions.py
"""
Database operations for managing user-specific permissions.
"""

from .connection import get_db
from .users import UsersDB # To get the list of users

class PermissionsDB:
    """Handles CRUD operations for the UserPermissions table."""

    def __init__(self):
        self.db = get_db()
        # Ensure the table exists (runs the SQL in Step 1 if needed)
        self._ensure_table()
        self.users_db = UsersDB()

    def _ensure_table(self):
        """Creates the UserPermissions table if it doesn't exist."""
        # This method attempts to run the SQL script from Step 1
        # Note: Table creation might fail if the DB user lacks permissions after initial setup.
        # It's generally better to create/alter tables manually via SQL management tools.
        # This is a fallback/initial setup helper.
        try:
            with self.db.get_connection() as conn:
                if not conn.check_table_exists('UserPermissions'):
                    print("Attempting to create UserPermissions table from permissions.py...")
                    # Simplified creation script (assumes SQL script from Step 1 was run)
                    create_script = """
                        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'UserPermissions')
                        BEGIN
                            CREATE TABLE UserPermissions (
                                permission_id INT IDENTITY(1,1) PRIMARY KEY,
                                username NVARCHAR(100) NOT NULL UNIQUE,
                                can_view_scheduling BIT DEFAULT 0 NOT NULL,
                                can_edit_scheduling BIT DEFAULT 0 NOT NULL,
                                can_view_downtime BIT DEFAULT 0 NOT NULL,
                                can_view_reports BIT DEFAULT 0 NOT NULL,
                                last_updated_by NVARCHAR(100),
                                last_updated_date DATETIME DEFAULT GETDATE()
                            );
                            CREATE INDEX IX_UserPermissions_Username ON UserPermissions(username);
                            PRINT 'UserPermissions table created successfully from Python.';
                        END
                    """
                    conn.execute_query(create_script) # Use execute_query for potentially complex script
        except Exception as e:
            print(f"Error ensuring UserPermissions table exists: {e}")


    def get_users_with_permissions(self):
        """
        Gets all users from UserLogins and joins their specific permissions
        from UserPermissions, defaulting if no specific permissions are set.
        """
        all_users = self.users_db.get_user_summary() # Get users who have logged in
        permissions_map = self._get_all_permissions_map()

        users_with_perms = []
        for user in all_users:
            username = user['username']
            perms = permissions_map.get(username, {
                'can_view_scheduling': False,
                'can_edit_scheduling': False,
                'can_view_downtime': False,
                'can_view_reports': False,
                # Add defaults for any new permissions here
            })
            # Combine user info with permissions
            combined_info = {**user, **perms, 'username': username} # Ensure username is present
            users_with_perms.append(combined_info)

        return users_with_perms

    def _get_all_permissions_map(self):
        """ Fetches all specific permissions into a dictionary keyed by username. """
        with self.db.get_connection() as conn:
            query = """
                SELECT
                    username, can_view_scheduling, can_edit_scheduling,
                    can_view_downtime, can_view_reports
                    -- Add new columns here
                FROM UserPermissions
            """
            results = conn.execute_query(query)
            perms_map = {}
            for row in results:
                # Convert BIT to Python bool
                perms_map[row['username']] = {
                    'can_view_scheduling': bool(row['can_view_scheduling']),
                    'can_edit_scheduling': bool(row['can_edit_scheduling']),
                    'can_view_downtime': bool(row['can_view_downtime']),
                    'can_view_reports': bool(row['can_view_reports']),
                    # Add new columns here
                }
            return perms_map

    def get_user_permissions(self, username):
        """ Gets specific permissions for a single user, returning defaults if not found. """
        with self.db.get_connection() as conn:
            query = """
                SELECT
                    can_view_scheduling, can_edit_scheduling,
                    can_view_downtime, can_view_reports
                    -- Add new columns here
                FROM UserPermissions
                WHERE username = ?
            """
            result = conn.execute_query(query, (username,))
            if result:
                 # Convert BIT to Python bool
                return {
                    'can_view_scheduling': bool(result[0]['can_view_scheduling']),
                    'can_edit_scheduling': bool(result[0]['can_edit_scheduling']),
                    'can_view_downtime': bool(result[0]['can_view_downtime']),
                    'can_view_reports': bool(result[0]['can_view_reports']),
                    # Add new columns here
                }
            else:
                # Return default permissions if user not in the table yet
                return {
                    'can_view_scheduling': False,
                    'can_edit_scheduling': False,
                    'can_view_downtime': False,
                    'can_view_reports': False,
                    # Add defaults for any new permissions here
                }

    def update_user_permissions(self, username, permissions_dict, updated_by):
        """
        Updates or inserts permissions for a specific user.
        permissions_dict should contain keys like 'can_view_scheduling' with boolean values.
        """
        with self.db.get_connection() as conn:
            # Check if user exists in the permissions table
            exists_query = "SELECT COUNT(*) as count FROM UserPermissions WHERE username = ?"
            result = conn.execute_query(exists_query, (username,))
            user_exists = result[0]['count'] > 0 if result else False

            if user_exists:
                # Build UPDATE statement
                set_clauses = []
                params = []
                for key, value in permissions_dict.items():
                    # Ensure key is a valid column name to prevent SQL injection
                    # (simple check, might need more robust validation)
                    if key in ['can_view_scheduling', 'can_edit_scheduling', 'can_view_downtime', 'can_view_reports']:
                         set_clauses.append(f"{key} = ?")
                         params.append(1 if value else 0) # Convert bool to 1 or 0 for SQL Server BIT

                if not set_clauses:
                    return False, "No valid permissions provided for update."

                set_clauses.append("last_updated_by = ?")
                params.append(updated_by)
                set_clauses.append("last_updated_date = GETDATE()")

                sql = f"UPDATE UserPermissions SET {', '.join(set_clauses)} WHERE username = ?"
                params.append(username)

                success = conn.execute_query(sql, params)
                message = "Permissions updated successfully." if success else "Failed to update permissions."
                return success, message
            else:
                # Build INSERT statement
                columns = ['username', 'last_updated_by', 'last_updated_date']
                placeholders = ['?', '?', 'GETDATE()']
                params = [username, updated_by]

                for key, value in permissions_dict.items():
                    if key in ['can_view_scheduling', 'can_edit_scheduling', 'can_view_downtime', 'can_view_reports']:
                        columns.append(key)
                        placeholders.append('?')
                        params.append(1 if value else 0)

                sql = f"INSERT INTO UserPermissions ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"

                success = conn.execute_query(sql, params)
                message = "Permissions set successfully." if success else "Failed to set permissions."
                return success, message

# Singleton instance
permissions_db = PermissionsDB()