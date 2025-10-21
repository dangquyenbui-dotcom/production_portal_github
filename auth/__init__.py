# auth/__init__.py
"""
Authentication package initialization
"""

# Import only the functions needed externally after Azure AD refactor
from .ad_auth import (
    authenticate_local_admin, # Keep for local admin fallback
    require_login,
    require_admin,
    require_user,
    require_scheduling_admin,
    require_scheduling_user
    # authenticate_user - Removed, no longer exists
    # get_user_groups - Removed, only used internally now
    # test_ad_connection - Removed, no longer applicable
)

# Update __all__ list to match the available imports
__all__ = [
    'authenticate_local_admin',
    'require_login',
    'require_admin',
    'require_user',
    'require_scheduling_admin',
    'require_scheduling_user'
]