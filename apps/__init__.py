import os
from datetime import timedelta
from flask import Flask, session, g
from flask_wtf.csrf import CSRFProtect
from importlib import import_module

from apps.config import Config
from apps.db import get_db_connection  # Ensure this is used somewhere or remove

# Initialize Flask extensions
csrf = CSRFProtect()

def register_extensions(app):
    """Initialize Flask extensions."""
    csrf.init_app(app)

def register_blueprints(app):
    """Register all blueprints dynamically from the apps module."""
    modules = [
        'authentication', 'home', 'pupils', 'classes', 'fathers', 'mothers',
        'guardians', 'subjects', 'teachers', 'gen_ids', 'study_years',
        'results', 'reports', 'grades', 'dorms', 'register', 'promote',
        'streams', 'rooms', 'stream_assign', 'categories', 'products',
        'p_restock', 'dorm_reg', 'sub_categories', 'sales', 'customers',
        'other_products', 'department_h_products', 'dep_restock', 'division',
        'subject_assign', 'results_update', 'add_marks','assessment','term',
        'classteacher_assign','grade_analysis','eot_reports','past_reports',
        'subject_comments','headmaster_comments','classteacher_comments','locations'
    ]

    for module_name in modules:
        module = import_module(f'apps.{module_name}.routes')
        app.register_blueprint(module.blueprint)

def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Set session lifetime
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

    # Register app components
    register_extensions(app)
    register_blueprints(app)

    @app.before_request
    def before_request():
        """Store user ID from session in the application context."""
        g.user_id = session.get('id')

    return app