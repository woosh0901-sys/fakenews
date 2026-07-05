import os
import sys

# Add the project root directory to python path so that we can import our modules
# (e.g. backend_app, fact_checker_by_url, etc.)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_app import app
