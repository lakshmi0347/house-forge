from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from firebase_admin import firestore
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os

user_bp = Blueprint('user', __name__)

def get_db():
    """Get database instance"""
    try:
        return firestore.client()
    except Exception as e:
        print(f"Error getting database: {e}")
        return None

@user_bp.route('/dashboard')
@login_required
def dashboard():
    """User Dashboard - Main page after login"""
    
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('index'))
    
    # Get user's projects
    projects_ref = db.collection('projects').where('user_id', '==', current_user.id).stream()
    projects = []
    for doc in projects_ref:
        project_data = doc.to_dict()
        project_data['id'] = doc.id
        projects.append(project_data)
    
    # Get recent estimates
    estimates_ref = db.collection('estimates').where('user_id', '==', current_user.id).limit(5).stream()
    estimates = []
    for doc in estimates_ref:
        estimate_data = doc.to_dict()
        estimate_data['id'] = doc.id
        estimates.append(estimate_data)
    
    # Get recent orders
    orders_ref = db.collection('orders').where('user_id', '==', current_user.id).limit(5).stream()
    orders = []
    for doc in orders_ref:
        order_data = doc.to_dict()
        order_data['id'] = doc.id
        orders.append(order_data)
    
    stats = {
        'total_projects': len(projects),
        'active_projects': len([p for p in projects if p.get('status') == 'active']),
        'total_estimates': len(estimates),
        'total_orders': len(orders)
    }
    
    return render_template('user/dashboard.html', 
                         projects=projects[:5],
                         estimates=estimates,
                         orders=orders,
                         stats=stats)

@user_bp.route('/profile')
@login_required
def profile():
    """User Profile Page"""
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.dashboard'))
    
    # Get user data from Firebase
    user_ref = db.collection('users').document(current_user.id)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        flash('User not found', 'error')
        return redirect(url_for('user.dashboard'))
    
    user_data = user_doc.to_dict()
    
    # Count user's projects
    projects_ref = db.collection('projects').where('user_id', '==', current_user.id).stream()
    project_count = len(list(projects_ref))
    
    return render_template('user/profile.html', 
                         user_data=user_data,
                         project_count=project_count)

@user_bp.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    """Update user profile information"""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone', '')
        location = request.form.get('location', '')
        
        user_ref = db.collection('users').document(current_user.id)
        user_ref.update({
            'name': name,
            'email': email,
            'phone': phone,
            'location': location,
            'updated_at': datetime.now().isoformat()
        })
        
        return jsonify({'success': True, 'message': 'Profile updated successfully'})
    
    except Exception as e:
        print(f"Error updating profile: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@user_bp.route('/upload_profile_picture', methods=['POST'])
@login_required
def upload_profile_picture():
    """Upload user profile picture"""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
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
        
        filename = secure_filename(f"{current_user.id}_{int(datetime.now().timestamp())}.{file_ext}")
        
        upload_folder = os.path.join('static', 'uploads', 'profiles')
        os.makedirs(upload_folder, exist_ok=True)
        
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        
        user_ref = db.collection('users').document(current_user.id)
        user_ref.update({
            'profile_picture': filename,
            'updated_at': datetime.now().isoformat()
        })
        
        return jsonify({'success': True, 'message': 'Profile picture uploaded successfully', 'filename': filename})
    
    except Exception as e:
        print(f"Error uploading profile picture: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@user_bp.route('/change_password', methods=['POST'])
@login_required
def change_password():
    """Change user password"""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        current_password = request.form.get('currentPassword')
        new_password = request.form.get('newPassword')
        
        user_ref = db.collection('users').document(current_user.id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        user_data = user_doc.to_dict()
        
        if not check_password_hash(user_data.get('password', ''), current_password):
            return jsonify({'success': False, 'message': 'Current password is incorrect'}), 400
        
        hashed_password = generate_password_hash(new_password)
        user_ref.update({
            'password': hashed_password,
            'updated_at': datetime.now().isoformat()
        })
        
        return jsonify({'success': True, 'message': 'Password changed successfully'})
    
    except Exception as e:
        print(f"Error changing password: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@user_bp.route('/projects')
@login_required
def projects():
    """View all projects"""
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.dashboard'))
    
    projects_ref = db.collection('projects').where('user_id', '==', current_user.id).stream()
    projects = []
    for doc in projects_ref:
        project_data = doc.to_dict()
        project_data['id'] = doc.id
        projects.append(project_data)
    
    return render_template('user/my_projects.html', projects=projects)

@user_bp.route('/create-project', methods=['GET', 'POST'])
@login_required
def create_project():
    """Create new construction project"""
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.dashboard'))
    
    if request.method == 'POST':
        from services.calculation_service import calculate_materials_and_cost
        
        square_feet = float(request.form.get('square_feet'))
        rooms = int(request.form.get('rooms'))
        floors = int(request.form.get('floors'))
        bathrooms = int(request.form.get('bathrooms', 2))
        budget_range = request.form.get('budget_range')
        
        estimation = calculate_materials_and_cost(
            square_feet, rooms, floors, bathrooms, budget_range
        )
        
        project_data = {
            'user_id': current_user.id,
            'title': request.form.get('title'),
            'square_feet': square_feet,
            'rooms': rooms,
            'floors': floors,
            'bathrooms': bathrooms,
            'location': request.form.get('location'),
            'property_type': request.form.get('property_type', 'residential'),
            'budget_range': budget_range,
            'description': request.form.get('description'),
            'status': 'planning',
            'created_at': datetime.now(),
            'estimation': estimation
        }
        
        doc_ref = db.collection('projects').add(project_data)
        project_id = doc_ref[1].id
        
        return render_template('user/project_created.html', 
                              project=project_data, 
                              estimation=estimation,
                              project_id=project_id)
    
    return render_template('user/create_project.html')

@user_bp.route('/project/<project_id>')
@login_required
def view_project(project_id):
    """View detailed project information with full estimation"""
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.projects'))
    
    try:
        project_doc = db.collection('projects').document(project_id).get()
        
        if not project_doc.exists:
            flash('Project not found', 'error')
            return redirect(url_for('user.projects'))
        
        project_data = project_doc.to_dict()
        
        if project_data.get('user_id') != current_user.id:
            flash('Access denied', 'error')
            return redirect(url_for('user.projects'))
        
        project_data['id'] = project_id
        estimation = project_data.get('estimation', {})
        
        return render_template(
            'user/project_detail.html',
            project=project_data,
            estimation=estimation
        )
                             
    except Exception as e:
        flash(f'Error loading project: {str(e)}', 'error')
        return redirect(url_for('user.projects'))

@user_bp.route('/project/<project_id>/download-pdf')
@login_required
def download_pdf(project_id):
    """Download project estimation as PDF"""
    from flask import send_file
    from services.pdf_service import generate_project_pdf
    
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.projects'))
    
    try:
        project_doc = db.collection('projects').document(project_id).get()
        
        if not project_doc.exists:
            flash('Project not found', 'error')
            return redirect(url_for('user.projects'))
        
        project_data = project_doc.to_dict()
        
        if project_data.get('user_id') != current_user.id:
            flash('Access denied', 'error')
            return redirect(url_for('user.projects'))
        
        estimation = project_data.get('estimation', {})
        pdf_buffer = generate_project_pdf(project_data, estimation)
        
        filename = f"{project_data.get('title', 'project').replace(' ', '_')}_estimation.pdf"
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('user.view_project', project_id=project_id))

@user_bp.route('/find-contractors')
@login_required
def find_contractors():
    """Browse and find verified contractors"""
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.dashboard'))
    
    try:
        contractors_ref = db.collection('contractors').where('verified', '==', True).where('active', '==', True).stream()
        contractors = []
        
        for doc in contractors_ref:
            contractor_data = doc.to_dict()
            contractor_data['id'] = doc.id
            contractors.append(contractor_data)
        
        contractors.sort(key=lambda x: x.get('rating', 0), reverse=True)
        
        return render_template('user/find_contractors.html', contractors=contractors)
        
    except Exception as e:
        flash(f'Error loading contractors: {str(e)}', 'error')
        return redirect(url_for('user.dashboard'))

@user_bp.route('/contractor/<contractor_id>')
@login_required
def view_contractor(contractor_id):
    """View contractor profile and details"""
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.find_contractors'))
    
    try:
        contractor_doc = db.collection('contractors').document(contractor_id).get()
        
        if not contractor_doc.exists:
            flash('Contractor not found', 'error')
            return redirect(url_for('user.find_contractors'))
        
        contractor_data = contractor_doc.to_dict()
        contractor_data['id'] = contractor_id
        
        return render_template('user/contractor_profile.html', contractor=contractor_data)
        
    except Exception as e:
        flash(f'Error loading contractor: {str(e)}', 'error')
        return redirect(url_for('user.find_contractors'))