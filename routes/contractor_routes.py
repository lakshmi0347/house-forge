from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from firebase_admin import firestore
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import json

contractor_bp = Blueprint('contractor', __name__)
db = firestore.client()

@contractor_bp.route('/dashboard')
@login_required
def dashboard():
    """Contractor Dashboard - Main page after login"""
    
    # Get contractor's submitted estimates
    estimates_ref = db.collection('estimates').where('contractor_id', '==', current_user.id).stream()
    estimates = []
    for doc in estimates_ref:
        estimate_data = doc.to_dict()
        estimate_data['id'] = doc.id
        estimates.append(estimate_data)
    
    # Get active projects
    active_projects_ref = db.collection('projects').where('contractor_id', '==', current_user.id).where('status', '==', 'active').stream()
    active_projects = []
    for doc in active_projects_ref:
        project_data = doc.to_dict()
        project_data['id'] = doc.id
        active_projects.append(project_data)
    
    # Get available projects (not assigned to anyone)
    available_projects_ref = db.collection('projects').where('status', '==', 'planning').limit(10).stream()
    available_projects = []
    for doc in available_projects_ref:
        project_data = doc.to_dict()
        project_data['id'] = doc.id
        available_projects.append(project_data)
    
    stats = {
        'total_estimates': len(estimates),
        'active_projects': len(active_projects),
        'completed_projects': current_user.completed_projects if hasattr(current_user, 'completed_projects') else 0,
        'rating': current_user.rating if hasattr(current_user, 'rating') else 0.0,
        'verified': current_user.verified if hasattr(current_user, 'verified') else False
    }
    
    return render_template('contractor/dashboard.html',
                         estimates=estimates[:5],
                         active_projects=active_projects,
                         available_projects=available_projects[:5],
                         stats=stats)

@contractor_bp.route('/profile')
@login_required
def profile():
    """Contractor Profile Page"""
    try:
        print("=" * 50)
        print("PROFILE ROUTE HIT")
        print(f"Current User ID: {current_user.id}")
        print(f"Current User Name: {getattr(current_user, 'name', 'NO NAME')}")
        print(f"Current User Role: {getattr(current_user, 'role', 'NO ROLE')}")
        print("=" * 50)
        
        # FIXED: Look in 'contractors' collection instead of 'users'
        contractor_ref = db.collection('contractors').document(current_user.id)
        contractor_doc = contractor_ref.get()
        
        print(f"Document exists: {contractor_doc.exists}")
        
        if not contractor_doc.exists:
            print("ERROR: Contractor document not found in Firebase!")
            print(f"Tried to find document with ID: {current_user.id}")
            flash('Contractor profile not found. Please contact support.', 'error')
            return redirect(url_for('contractor.dashboard'))
        
        contractor_data = contractor_doc.to_dict()
        print(f"Contractor data loaded successfully")
        print(f"Name: {contractor_data.get('name')}")
        print(f"Company: {contractor_data.get('company_name')}")
        print(f"Email: {contractor_data.get('email')}")

         # ✅ CONVERT FIREBASE DATETIME TO STRING
        if 'created_at' in contractor_data and contractor_data['created_at']:
            try:
                # Convert Firebase datetime to string
                contractor_data['created_at'] = contractor_data['created_at'].strftime('%Y-%m-%d')
            except:
                contractor_data['created_at'] = 'N/A'
        else:
            contractor_data['created_at'] = 'N/A'

        contractor_data['years_experience'] = contractor_data.get('experience', 0)
        contractor_data['verified'] = contractor_data.get('active', False)
        
        # Count active projects
        try:
            active_projects_ref = db.collection('projects').where('contractor_id', '==', current_user.id).where('status', '==', 'active').stream()
            active_projects_count = len(list(active_projects_ref))
            print(f"Active projects count: {active_projects_count}")
        except Exception as e:
            print(f"Error counting projects: {e}")
            active_projects_count = 0
        
        # Set defaults for missing fields
        contractor_data.setdefault('name', '')
        contractor_data.setdefault('email', '')
        contractor_data.setdefault('company_name', '')
        contractor_data.setdefault('phone', '')
        contractor_data.setdefault('location', '')
        contractor_data.setdefault('bio', '')
        contractor_data.setdefault('license_number', '')
        contractor_data.setdefault('years_experience', contractor_data.get('experience', 0))  # Note: your DB uses 'experience'
        contractor_data.setdefault('specializations', [])
        contractor_data.setdefault('verified', contractor_data.get('active', False))  # Note: your DB uses 'active'
        contractor_data.setdefault('rating', 0.0)
        contractor_data.setdefault('completed_projects', 0)
        contractor_data.setdefault('profile_picture', '')
        contractor_data.setdefault('created_at', '')
        
        print("Rendering template...")
        return render_template('contractor/profile.html',
                             contractor_data=contractor_data,
                             active_projects_count=active_projects_count)
    
    except Exception as e:
        print("=" * 50)
        print(f"EXCEPTION IN PROFILE ROUTE: {e}")
        print("=" * 50)
        import traceback
        traceback.print_exc()
        flash('An error occurred while loading your profile', 'error')
        return redirect(url_for('contractor.dashboard'))

@contractor_bp.route('/update_business_info', methods=['POST'])
@login_required
def update_business_info():
    """Update contractor business information"""
    try:
        company_name = request.form.get('company_name')
        license_number = request.form.get('license_number', '')
        years_experience = int(request.form.get('years_experience', 0))
        phone = request.form.get('phone')
        location = request.form.get('location')
        bio = request.form.get('bio', '')
        specializations = json.loads(request.form.get('specializations', '[]'))
        
        contractor_ref = db.collection('contractor').document(current_user.id)
        contractor_ref.update({
            'company_name': company_name,
            'license_number': license_number,
            'years_experience': years_experience,
            'phone': phone,
            'location': location,
            'bio': bio,
            'specializations': specializations,
            'updated_at': datetime.now().isoformat()
        })
        
        return jsonify({'success': True, 'message': 'Business information updated successfully'})
    
    except Exception as e:
        print(f"Error updating business info: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@contractor_bp.route('/update_personal_info', methods=['POST'])
@login_required
def update_personal_info():
    """Update contractor personal information"""
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        
        contractor_ref = db.collection('contractor').document(current_user.id)
        contractor_ref.update({
            'name': name,
            'email': email,
            'updated_at': datetime.now().isoformat()
        })
        
        return jsonify({'success': True, 'message': 'Personal information updated successfully'})
    
    except Exception as e:
        print(f"Error updating personal info: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@contractor_bp.route('/upload_profile_picture', methods=['POST'])
@login_required
def upload_profile_picture():
    """Upload contractor profile picture"""
    try:
        if 'profile_picture' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
        
        file = request.files['profile_picture']
        
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        
        if file_ext not in allowed_extensions:
            return jsonify({'success': False, 'message': 'Invalid file type. Only PNG, JPG, JPEG, and GIF allowed'}), 400
        
        filename = secure_filename(f"contractor_{current_user.id}_{int(datetime.now().timestamp())}.{file_ext}")
        
        upload_folder = os.path.join('static', 'uploads', 'profiles')
        os.makedirs(upload_folder, exist_ok=True)
        
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        
        contractor_ref = db.collection('contractor').document(current_user.id)
        contractor_ref.update({
            'profile_picture': filename,
            'updated_at': datetime.now().isoformat()
        })
        
        return jsonify({'success': True, 'message': 'Profile picture uploaded successfully', 'filename': filename})
    
    except Exception as e:
        print(f"Error uploading profile picture: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@contractor_bp.route('/change_password', methods=['POST'])
@login_required
def change_password():
    """Change contractor password"""
    try:
        current_password = request.form.get('currentPassword')
        new_password = request.form.get('newPassword')
        
        contractor_ref = db.collection('contractor').document(current_user.id)
        contractor_doc = contractor_ref.get()
        
        if not contractor_doc.exists:
            return jsonify({'success': False, 'message': 'Contractor not found'}), 404
        
        contractor_data = contractor_doc.to_dict()
        
        if not check_password_hash(contractor_data.get('password', ''), current_password):
            return jsonify({'success': False, 'message': 'Current password is incorrect'}), 400
        
        hashed_password = generate_password_hash(new_password)
        contractor_ref.update({
            'password': hashed_password,
            'updated_at': datetime.now().isoformat()
        })
        
        return jsonify({'success': True, 'message': 'Password changed successfully'})
    
    except Exception as e:
        print(f"Error changing password: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@contractor_bp.route('/browse-projects')
@login_required
def browse_projects():
    """Browse available projects"""
    projects_ref = db.collection('projects').where('status', '==', 'planning').stream()
    projects = []
    for doc in projects_ref:
        project_data = doc.to_dict()
        project_data['id'] = doc.id
        projects.append(project_data)
    
    return render_template('contractor/browse_projects.html', projects=projects)

@contractor_bp.route('/my-projects')
@login_required
def my_projects():
    """View contractor's active projects"""
    projects_ref = db.collection('projects').where('contractor_id', '==', current_user.id).stream()
    projects = []
    for doc in projects_ref:
        project_data = doc.to_dict()
        project_data['id'] = doc.id
        projects.append(project_data)
    
    return render_template('contractor/active_projects.html', projects=projects)

@contractor_bp.route('/submit-estimate/<project_id>', methods=['GET', 'POST'])
@login_required
def submit_estimate(project_id):
    """Submit estimate for a project"""
    if request.method == 'POST':
        estimate_data = {
            'project_id': project_id,
            'contractor_id': current_user.id,
            'contractor_name': current_user.name,
            'total_cost': float(request.form.get('total_cost')),
            'duration_days': int(request.form.get('duration_days')),
            'description': request.form.get('description'),
            'status': 'pending',
            'created_at': datetime.now()
        }
        
        db.collection('estimates').add(estimate_data)
        flash('Estimate submitted successfully!', 'success')
        return redirect(url_for('contractor.browse_projects'))
    
    project_doc = db.collection('projects').document(project_id).get()
    if not project_doc.exists:
        flash('Project not found', 'error')
        return redirect(url_for('contractor.browse_projects'))
    
    project = project_doc.to_dict()
    project['id'] = project_doc.id
    
    return render_template('contractor/submit_estimate.html', project=project)