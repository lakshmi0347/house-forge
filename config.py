import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base configuration"""
    
    # Flask Settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'house-forge-default-secret-key'
    FLASK_APP = os.environ.get('FLASK_APP') or 'app.py'
    
    # Firebase Settings
    FIREBASE_CONFIG = 'firebase_config.json'
    
    # Upload Settings
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}
    
    # Pagination
    ITEMS_PER_PAGE = 10
    
    # Email Settings (for later use)
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    
    # Material Price Ranges (default prices in INR)
    MATERIAL_PRICES = {
        'cement': {'low': 350, 'medium': 450, 'high': 600},
        'steel': {'low': 50, 'medium': 65, 'high': 80},
        'bricks': {'low': 8, 'medium': 12, 'high': 18},
        'sand': {'low': 40, 'medium': 55, 'high': 70},
        'aggregate': {'low': 45, 'medium': 60, 'high': 75},
        'wood': {'low': 500, 'medium': 800, 'high': 1200},
        'tiles': {'low': 30, 'medium': 50, 'high': 80},
        'paint': {'low': 200, 'medium': 350, 'high': 500},
        'electrical': {'low': 150, 'medium': 250, 'high': 400},
        'plumbing': {'low': 180, 'medium': 300, 'high': 450}
    }
    
    # Labor cost percentage of material cost
    LABOR_COST_PERCENTAGE = 0.30  # 30%
    
    # User Roles
    ROLES = {
        'USER': 'user',
        'ADMIN': 'admin',
        'CONTRACTOR': 'contractor',
        'SUPPLIER': 'supplier'
    }

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}