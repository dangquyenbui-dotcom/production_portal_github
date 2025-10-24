# routes/__init__.py
"""
Routes package initialization
All route blueprints are imported and registered in app.py
"""

from .main import main_bp
from .downtime import downtime_bp
from .erp_routes import erp_bp
from .scheduling import scheduling_bp
# from .reports import reports_bp # <-- REMOVE THIS LINE
from .reports import reports_bp # <-- ADD THIS LINE (imports the new combined blueprint)
from .bom import bom_bp
from .po import po_bp
from .mrp import mrp_bp
from .sales import sales_bp
from .jobs import jobs_bp
from . import admin

__all__ = [
    'main_bp',
    'downtime_bp',
    'erp_bp',
    'scheduling_bp',
    'reports_bp', # <-- Keep this, it now refers to the combined blueprint
    'admin',
    'bom_bp',
    'po_bp',
    'mrp_bp',
    'sales_bp',
    'jobs_bp'
]