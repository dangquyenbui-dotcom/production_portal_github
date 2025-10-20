# auth/__init__.py
"""
Authentication package initialization
"""

# <<<--- VERIFY THIS IMPORT STATEMENT --- >>>
from .ad_auth import (
    authenticate_user,
    get_user_groups,       # It should be listed here
    require_login,
    require_admin,
    require_user,
    require_scheduling_admin,
    require_scheduling_user,
    require_portal_admin,
    require_reports_user,
    test_ad_connection
)

__all__ = [
    'authenticate_user',
    'get_user_groups',       # And exported here
    'require_login',
    'require_admin',
    'require_user',
    'require_scheduling_admin',
    'require_scheduling_user',
    'require_portal_admin',
    'require_reports_user',
    'test_ad_connection'
]