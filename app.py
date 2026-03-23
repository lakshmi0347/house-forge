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
login_manager.login_view = 'auth.login'          # ✅ FIXED: was 'login', must be 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'error'   # ✅ ADDED: flash category for login message

# Initialize Firebase - Render safe
db = None
try:
    if not firebase_admin._apps:
        if os.environ.get("FIREBASE_CONFIG"):
            # 🔹 Render / Production
            firebase_config = json.loads(os.environ.get("FIREBASE_CONFIG"))
        else:
            # 🔹 Local development
            with open(app.config['FIREBASE_CONFIG'], 'r', encoding='utf-8-sig') as f:
                firebase_config = json.load(f)

        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred)
        print("✅ Firebase initialized successfully!")
    else:
        print("✅ Firebase already initialized!")

    db = firestore.client()
    print("✅ Firestore client ready!")

except Exception as e:
    print(f"❌ Firebase initialization error: {e}")
    db = None

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    """Load user from database"""
    if db is None:
        print("⚠️  Cannot load user - database not connected")
        return None
    
    try:
        # Check all collections for the user
        for collection in ['users', 'admins', 'contractors', 'suppliers']:
            user_doc = db.collection(collection).document(user_id).get()
            if user_doc.exists:
                from models.user import User
                return User(user_doc.id, user_doc.to_dict())
    except Exception as e:
        print(f"Error loading user: {e}")
    
    return None

# ─── Import and register blueprints ───────────────────────────────────────────
from routes.auth import auth_bp
from routes.user_routes import user_bp
from routes.contractor_routes import contractor_bp
from routes.supplier_routes import supplier_bp
from routes.admin_routes import admin_bp
from routes.viewer_routes import viewer_bp
from routes.payment_routes import payment_bp

app.register_blueprint(auth_bp)                              # /login, /register, /logout
app.register_blueprint(user_bp,        url_prefix='/user')
app.register_blueprint(contractor_bp,  url_prefix='/contractor')
app.register_blueprint(supplier_bp,    url_prefix='/supplier')
app.register_blueprint(admin_bp,       url_prefix='/admin')
app.register_blueprint(viewer_bp,      url_prefix='/viewer')
app.register_blueprint(payment_bp, url_prefix='/payment')

# ─── Home route ───────────────────────────────────────────────────────────────
@app.route('/')
def index():
    """Landing page - redirect logged-in users to their dashboard"""
    if current_user.is_authenticated:
        role = getattr(current_user, 'role', None)
        if role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif role == 'contractor':
            return redirect(url_for('contractor.dashboard'))
        elif role == 'supplier':
            return redirect(url_for('supplier.dashboard'))
        else:
            return redirect(url_for('user.dashboard'))
    return render_template('index.html')

# ─── Convenience redirects so /login and /register work as bare URLs ──────────
@app.route('/login')
def login_redirect():
    return redirect(url_for('auth.login'))

@app.route('/register')
def register_redirect():
    return redirect(url_for('auth.register'))

# ─── Test route ───────────────────────────────────────────────────────────────
@app.route('/test')
def test():
    """Test route to verify setup"""
    db_status = 'Connected' if db else 'Not Connected'
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
    <p>✅ Firebase status: {db_status}</p>
    <p>📊 Database: {doc_count}</p>
    <br>
    <a href="/">Home</a> | 
    <a href="/login">Login</a> | 
    <a href="/register">Register</a>
    '''

# ─── Error handlers ───────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

# ─── Context processors ───────────────────────────────────────────────────────
@app.context_processor
def inject_globals():
    return {
        'app_name': 'House-Forge',
        'current_year': 2024
    }

@app.context_processor
def inject_user_data():
    """Inject user profile data into all templates"""
    if current_user.is_authenticated:
        try:
            if db is not None:
                # Check all collections since role may vary
                role = getattr(current_user, 'role', 'user')
                collection_map = {
                    'user': 'users',
                    'contractor': 'contractors',
                    'supplier': 'suppliers',
                    'admin': 'admins'
                }
                collection = collection_map.get(role, 'users')
                user_ref = db.collection(collection).document(current_user.id)
                user_doc = user_ref.get()
                
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    return {
                        'user_profile_picture': user_data.get('profile_picture'),
                        'user_data': user_data
                    }
        except Exception as e:
            print(f"⚠️ Error loading user data: {e}")
    
    return {'user_profile_picture': None, 'user_data': {}}

# ─── Run ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    os.makedirs(app.config.get('UPLOAD_FOLDER', 'static/uploads'), exist_ok=True)
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