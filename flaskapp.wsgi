import sys
import logging
import os

# Activate virtual environment
activate_this = '/var/www/html/medicalChatbot/myenv/bin/activate_this.py'
with open(activate_this) as file_:
    exec(file_.read(), dict(__file__=activate_this))

# Add project directory to sys.paths
sys.path.insert(0, '/var/www/html/medicalChatbot')

# Set environment variables (optional but good)
os.environ['FLASK_ENV'] = 'production'

# Import Flask app
from app import app as application

# Logging
logging.basicConfig(stream=sys.stderr)
