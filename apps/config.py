import random
import string
import os

class Config:
    """Base configuration class."""
    # Absolute path to the current directory
    basedir = os.path.abspath(os.path.dirname(__file__))

    # Upload folder paths
    UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif','xlsx', 'xls'}

    # Secret key for Flask (generated securely)
    SECRET_KEY = ''.join(random.choices(string.ascii_letters + string.digits, k=32))

    # MySQL Configuration
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.getenv('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
    MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'shpsk')

    @staticmethod
    def init_app(app):
        """Initialize the app with the configuration."""
        app.config.from_object(Config)
        # Ensure the upload folder exists
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)