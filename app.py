from flask import Flask, render_template, redirect, url_for, flash, session
from flask_login import LoginManager, current_user
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect
import firebase_admin
from firebase_admin import credentials, firestore
import os
from config import config

# Initialize Flask app
app = Flask(__name__)

# Load configuration
env = os.environ.get('FLASK_ENV', 'development')
app.config.from_object(config[env])

# Initialize extensions
bcrypt = Bcrypt(app)
# csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# Initialize Firebase
try:
    cred = credentials.Certificate(app.config['FIREBASE_CONFIG'])
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Firebase initialized successfully!")
except Exception as e:
    print(f"❌ Firebase initialization error: {e}")
    db = None

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    """Load user from database"""
    if db is None:
        return None
    
    try:
        user_doc = db.collection('users').document(user_id).get()
        if user_doc.exists:
            from models.user import User
            return User(user_doc.id, user_doc.to_dict())
        
        # Check other collections for different roles
        for collection in ['admins', 'contractors', 'suppliers']:
            user_doc = db.collection(collection).document(user_id).get()
            if user_doc.exists:
                from models.user import User
                return User(user_doc.id, user_doc.to_dict())
    except Exception as e:
        print(f"Error loading user: {e}")
    
    return None

# Import and register blueprints
from routes.auth import auth_bp
from routes.user_routes import user_bp
from routes.contractor_routes import contractor_bp
from routes.supplier_routes import supplier_bp
from routes.admin_routes import admin_bp

app.register_blueprint(auth_bp)
app.register_blueprint(user_bp, url_prefix='/user')
app.register_blueprint(contractor_bp, url_prefix='/contractor')
app.register_blueprint(supplier_bp, url_prefix='/supplier')
app.register_blueprint(admin_bp, url_prefix='/admin')

# (We'll add other modules later)
# from routes.user_routes import user_bp
# from routes.admin_routes import admin_bp
# from routes.contractor_routes import contractor_bp
# from routes.supplier_routes import supplier_bp

# app.register_blueprint(user_bp, url_prefix='/user')
# app.register_blueprint(admin_bp, url_prefix='/admin')
# app.register_blueprint(contractor_bp, url_prefix='/contractor')
# app.register_blueprint(supplier_bp, url_prefix='/supplier')

# Home route
@app.route('/')
def index():
    """Landing page"""
    return render_template('index.html')

# Test route to verify Flask is working
@app.route('/test')
def test():
    """Test route to verify setup"""
    return '''
    <h1>🎉 House-Forge is Running!</h1>
    <p>✅ Flask is working</p>
    <p>✅ Configuration loaded</p>
    <p>✅ Firebase status: {}</p>
    <br>
    <a href="/">Go to Home</a>
    '''.format('Connected' if db else 'Not Connected')

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return render_template('500.html'), 500

# Context processor to make variables available in all templates
@app.context_processor
def inject_globals():
    """Inject global variables into templates"""
    return {
        'app_name': 'House-Forge',
        'current_year': 2024
    }

if __name__ == '__main__':
    # Create upload folders if they don't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs('static/uploads/profiles', exist_ok=True)
    os.makedirs('static/uploads/documents', exist_ok=True)
    os.makedirs('static/uploads/portfolio', exist_ok=True)
    
    print("=" * 50)
    print("🏗️  HOUSE-FORGE - Construction Planning System")
    print("=" * 50)
    print(f"🌍 Running on: http://127.0.0.1:5000")
    print(f"📝 Environment: {env}")
    print(f"🔥 Firebase: {'✅ Connected' if db else '❌ Not Connected'}")
    print("=" * 50)
    
    app.run(debug=True, port=5000)