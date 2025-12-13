# routes/__init__.py
"""
Shared database instance for all route modules
"""

# This will be set by app.py after Firebase initialization
db = None

def init_db(database):
    """Initialize the shared database instance"""
    global db
    db = database