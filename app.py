from flask import Flask, render_template, redirect, url_for, flash, session
from flask_login import LoginManager, current_user
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
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

# Initialize Firebase - Check if already initialized
db = None
try:
    # Check if Firebase is already initialized
    if not firebase_admin._apps:
        # Read the config file with utf-8-sig to remove BOM
        with open(app.config['FIREBASE_CONFIG'], 'r', encoding='utf-8-sig') as f:
            firebase_config = json.load(f)
        
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred)
        print("✅ Firebase initialized successfully!")
    else:
        print("✅ Firebase already initialized!")
    
    # Get Firestore client
    db = firestore.client()
    print("✅ Firestore client ready!")
    
except Exception as e:
    print(f"❌ Firebase initialization error: {e}")
    import traceback
    traceback.print_exc()
    db = None

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    """Load user from database"""
    if db is None:
        print("⚠️  Cannot load user - database not connected")
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

# Home route
@app.route('/')
def index():
    """Landing page"""
    return render_template('index.html')

# Test route to verify Flask is working
@app.route('/test')
def test():
    """Test route to verify setup"""
    db_status = 'Connected' if db else 'Not Connected'
    
    # Try to count documents if connected
    doc_count = "N/A"
    if db:
        try:
            users = len(list(db.collection('users').limit(10).stream()))
            contractors = len(list(db.collection('contractors').limit(10).stream()))
            suppliers = len(list(db.collection('suppliers').limit(10).stream()))
            doc_count = f"Users: {users}, Contractors: {contractors}, Suppliers: {suppliers}"
        except:
            doc_count = "Error reading collections"
    
    return f'''
    <h1>🎉 House-Forge is Running!</h1>
    <p>✅ Flask is working</p>
    <p>✅ Configuration loaded</p>
    <p>✅ Firebase status: {db_status}</p>
    <p>📊 Database contents: {doc_count}</p>
    <br>
    <a href="/">Go to Home</a> | <a href="/login">Login</a> | <a href="/register">Register</a>
    '''

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

@app.context_processor
def inject_user_data():
    """Inject user data from Firebase into all templates"""
    if current_user.is_authenticated:
        try:
            if db is not None:
                user_ref = db.collection('users').document(current_user.id)
                user_doc = user_ref.get()
                
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    profile_picture = user_data.get('profile_picture')
                    
                    # Debug print
                    print(f"📸 Loading profile picture for {current_user.name}: {profile_picture}")
                    
                    return {
                        'user_profile_picture': profile_picture,
                        'user_data': user_data
                    }
        except Exception as e:
            print(f"⚠️ Error loading user data in context processor: {e}")
    
    return {'user_profile_picture': None, 'user_data': {}}

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
    
    if db:
        try:
            # Count documents
            users_count = len(list(db.collection('users').limit(10).stream()))
            contractors_count = len(list(db.collection('contractors').limit(10).stream()))
            suppliers_count = len(list(db.collection('suppliers').limit(10).stream()))
            print(f"📊 Database: {users_count} users, {contractors_count} contractors, {suppliers_count} suppliers")
        except Exception as e:
            print(f"⚠️  Could not count documents: {e}")
    
    print("=" * 50)
    
    app.run(debug=True, port=5000)