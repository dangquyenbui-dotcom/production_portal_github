# routes/reports/__init__.py
"""
Initializes the reports package and combines report blueprints.
"""

from flask import Blueprint

# Import individual report blueprints
from .hub import reports_hub_bp
from .downtime_summary import downtime_summary_bp
from .shipment_forecast import shipment_forecast_bp
from .coc import coc_report_bp

# Create the main reports blueprint with the '/reports' prefix
reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

# Register the individual blueprints onto the main reports blueprint
# The routes defined in each blueprint will be relative to '/reports'
reports_bp.register_blueprint(reports_hub_bp)
reports_bp.register_blueprint(downtime_summary_bp)
reports_bp.register_blueprint(shipment_forecast_bp)
reports_bp.register_blueprint(coc_report_bp)

# Export the combined blueprint for registration in app.py
__all__ = ['reports_bp']