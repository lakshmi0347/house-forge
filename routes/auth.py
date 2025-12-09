from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from firebase_admin import firestore
from models.user import User
from datetime import datetime
import re

auth_bp = Blueprint('auth', __name__)
db = firestore.client()

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Validate phone number (Indian format)"""
    pattern = r'^[6-9]\d{9}$'
    return re.match(pattern, phone) is not None

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page for all users"""
    if current_user.is_authenticated:
        # Redirect based on role
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif current_user.role == 'contractor':
            return redirect(url_for('contractor.dashboard'))
        elif current_user.role == 'supplier':
            return redirect(url_for('supplier.dashboard'))
        else:
            return redirect(url_for('user.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        # Validate inputs
        if not email or not password:
            flash('Please fill in all fields', 'error')
            return render_template('login.html')
        
        if not validate_email(email):
            flash('Invalid email format', 'error')
            return render_template('login.html')
        
        try:
            # Search in all collections
            collections = ['users', 'admins', 'contractors', 'suppliers']
            user_doc = None
            user_data = None
            
            for collection in collections:
                users_ref = db.collection(collection)
                query = users_ref.where('email', '==', email).limit(1).stream()
                
                for doc in query:
                    user_doc = doc
                    user_data = doc.to_dict()
                    break
                
                if user_doc:
                    break
            
            # Check if user exists
            if not user_doc or not user_data:
                flash('Invalid email or password', 'error')
                return render_template('login.html')
            
            # Verify password
            if not check_password_hash(user_data.get('password', ''), password):
                flash('Invalid email or password', 'error')
                return render_template('login.html')
            
            # Check if account is active
            if not user_data.get('active', True):
                flash('Your account has been deactivated. Please contact admin.', 'error')
                return render_template('login.html')
            
            # Create user object and login
            user = User(user_doc.id, user_data)
            login_user(user, remember=True)
            
            # Update last login
            db.collection(collection).document(user_doc.id).update({
                'last_login': datetime.now()
            })
            
            flash(f'Welcome back, {user.name}!', 'success')
            
            # Redirect based on role
            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user.role == 'contractor':
                return redirect(url_for('contractor.dashboard'))
            elif user.role == 'supplier':
                return redirect(url_for('supplier.dashboard'))
            else:
                return redirect(url_for('user.dashboard'))
                
        except Exception as e:
            flash(f'Login error: {str(e)}', 'error')
            return render_template('login.html')
    
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page with role selection"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'user')
        company_name = request.form.get('company_name', '').strip() or name
        experience = request.form.get('experience', 0)
        license_number = request.form.get('license_number', '').strip()
        gst_number = request.form.get('gst_number', '').strip()
        business_type = request.form.get('business_type', '').strip()
        errors = []
        
        if not name or len(name) < 3:
            errors.append('Name must be at least 3 characters')
        
        if not validate_email(email):
            errors.append('Invalid email format')
        
        if not validate_phone(phone):
            errors.append('Invalid phone number (10 digits starting with 6-9)')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters')
        
        if password != confirm_password:
            errors.append('Passwords do not match')
        
        if role not in ['user', 'contractor', 'supplier']:
            errors.append('Invalid role selected')
        
        # Role-specific validation
        if role in ['contractor', 'supplier']:
            if not company_name:
                errors.append('Company name is required')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('register.html')
        
        try:
            # Check if email already exists
            collections = ['users', 'admins', 'contractors', 'suppliers']
            for collection in collections:
                existing = db.collection(collection).where('email', '==', email).limit(1).stream()
                if any(existing):
                    flash('Email already registered', 'error')
                    return render_template('register.html')
            
            # Determine collection based on role
            if role == 'user':
                collection = 'users'
            elif role == 'contractor':
                collection = 'contractors'
            elif role == 'supplier':
                collection = 'suppliers'
            
            # Create user data
            user_data = {
                'name': name,
                'email': email,
                'phone': phone,
                'password': generate_password_hash(password),
                'role': role,
                'created_at': datetime.now(),
                'active': True,
                'verified': False if role in ['contractor', 'supplier'] else True
            }
            
            # Add role-specific fields
            if role == 'contractor':
                user_data.update({
                    'company_name': company_name,
                    'experience': int(experience),
                    'license_number': license_number,
                    'rating': 0.0,
                    'completed_projects': 0
                })
            elif role == 'supplier':
                user_data.update({
                    'company_name': company_name,
                    'business_type': business_type,
                    'gst_number': gst_number,
                    'rating': 0.0
                })
            
            # Add to database
            db.collection(collection).add(user_data)
            
            if role in ['contractor', 'supplier']:
                flash('Registration successful! Your account will be verified by admin soon.', 'success')
            else:
                flash('Registration successful! Please login.', 'success')
            
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            flash(f'Registration error: {str(e)}', 'error')
            return render_template('register.html')
    
    return render_template('register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """Logout user"""
    logout_user()
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('index'))