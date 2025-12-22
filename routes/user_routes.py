from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from firebase_admin import firestore
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os

user_bp = Blueprint('user', __name__)
db = firestore.client()

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

@user_bp.route('/project/<project_id>/bids')
@login_required
def project_bids(project_id):
    """View all bids for a specific project"""
    db = get_db()  # ← ADD THIS LINE
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.projects'))
    
    try:
        # Get project
        project_doc = db.collection('projects').document(project_id).get()
        
        if not project_doc.exists:
            flash('Project not found', 'error')
            return redirect(url_for('user.projects'))
        
        project_data = project_doc.to_dict()
        
        # Check ownership
        if project_data.get('user_id') != current_user.id:
            flash('Access denied', 'error')
            return redirect(url_for('user.projects'))
        
        project_data['id'] = project_id
        
        # Get all bids for this project
        bids_ref = db.collection('bids').where('project_id', '==', project_id).stream()
        bids = []
        
        for doc in bids_ref:
            bid_data = doc.to_dict()
            bid_data['id'] = doc.id
            bids.append(bid_data)
        
        # Sort by created_at
        bids.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)
        
        # Count by status
        pending = len([b for b in bids if b.get('status') == 'pending'])
        accepted = len([b for b in bids if b.get('status') == 'accepted'])
        rejected = len([b for b in bids if b.get('status') == 'rejected'])
        
        stats = {
            'total': len(bids),
            'pending': pending,
            'accepted': accepted,
            'rejected': rejected
        }
        
        return render_template('user/project_bids.html', 
                             project=project_data, 
                             bids=bids, 
                             stats=stats)
        
    except Exception as e:
        flash(f'Error loading bids: {str(e)}', 'error')
        return redirect(url_for('user.projects'))

@user_bp.route('/bid/<bid_id>/accept', methods=['POST'])
@login_required
def accept_bid(bid_id):
    """Accept a bid and assign contractor to project"""
    db = get_db()  # ← ADD THIS LINE
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.projects'))
    
    try:
        bid_doc = db.collection('bids').document(bid_id).get()
        
        if not bid_doc.exists:
            flash('Bid not found', 'error')
            return redirect(url_for('user.projects'))
        
        bid_data = bid_doc.to_dict()
        
        # Get project to verify ownership
        project_doc = db.collection('projects').document(bid_data.get('project_id')).get()
        project_data = project_doc.to_dict()
        
        if project_data.get('user_id') != current_user.id:
            flash('Access denied', 'error')
            return redirect(url_for('user.projects'))
        
        # Update bid status to accepted
        db.collection('bids').document(bid_id).update({
            'status': 'accepted',
            'accepted_at': datetime.now(),
            'updated_at': datetime.now()
        })
        
        # Reject all other bids for this project
        other_bids = db.collection('bids').where('project_id', '==', bid_data.get('project_id')).stream()
        for other_bid in other_bids:
            if other_bid.id != bid_id and other_bid.to_dict().get('status') == 'pending':
                db.collection('bids').document(other_bid.id).update({
                    'status': 'rejected',
                    'rejected_at': datetime.now(),
                    'updated_at': datetime.now()
                })
        
        # Update project with contractor info and change status to active
        db.collection('projects').document(bid_data.get('project_id')).update({
            'contractor_id': bid_data.get('contractor_id'),
            'contractor_name': bid_data.get('contractor_name'),
            'contractor_company': bid_data.get('contractor_company'),
            'agreed_cost': bid_data.get('total_cost'),
            'agreed_duration': bid_data.get('duration_days'),
            'status': 'active',
            'started_at': datetime.now(),
            'updated_at': datetime.now()
        })
        
        flash('Bid accepted! Contractor has been assigned to your project.', 'success')
        return redirect(url_for('user.project_bids', project_id=bid_data.get('project_id')))
        
    except Exception as e:
        flash(f'Error accepting bid: {str(e)}', 'error')
        return redirect(url_for('user.projects'))

@user_bp.route('/bid/<bid_id>/reject', methods=['POST'])
@login_required
def reject_bid(bid_id):
    """Reject a bid"""
    db = get_db()  # ← ADD THIS LINE
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.projects'))
    
    try:
        bid_doc = db.collection('bids').document(bid_id).get()
        
        if not bid_doc.exists:
            flash('Bid not found', 'error')
            return redirect(url_for('user.projects'))
        
        bid_data = bid_doc.to_dict()
        
        # Get project to verify ownership
        project_doc = db.collection('projects').document(bid_data.get('project_id')).get()
        project_data = project_doc.to_dict()
        
        if project_data.get('user_id') != current_user.id:
            flash('Access denied', 'error')
            return redirect(url_for('user.projects'))
        
        # Check if bid is still pending
        if bid_data.get('status') != 'pending':
            flash('Only pending bids can be rejected', 'error')
            return redirect(url_for('user.project_bids', project_id=bid_data.get('project_id')))
        
        # Update bid status to rejected
        db.collection('bids').document(bid_id).update({
            'status': 'rejected',
            'rejected_at': datetime.now(),
            'updated_at': datetime.now()
        })
        
        flash('Bid rejected successfully', 'success')
        return redirect(url_for('user.project_bids', project_id=bid_data.get('project_id')))
        
    except Exception as e:
        flash(f'Error rejecting bid: {str(e)}', 'error')
        return redirect(url_for('user.projects'))

# Add these routes to your existing user_routes.py file

@user_bp.route('/find-suppliers')
@login_required
def find_suppliers():
    """Browse and find verified suppliers"""
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.dashboard'))
    
    try:
        suppliers_ref = db.collection('suppliers').where('verified', '==', True).where('active', '==', True).stream()
        suppliers = []
        
        for doc in suppliers_ref:
            supplier_data = doc.to_dict()
            supplier_data['id'] = doc.id
            
            # Count materials offered by this supplier
            materials_ref = db.collection('materials').where('supplier_id', '==', doc.id).stream()
            supplier_data['materials_count'] = len(list(materials_ref))
            
            suppliers.append(supplier_data)
        
        # Sort by rating descending
        suppliers.sort(key=lambda x: x.get('rating', 0), reverse=True)
        
        return render_template('user/find_suppliers.html', suppliers=suppliers)
        
    except Exception as e:
        flash(f'Error loading suppliers: {str(e)}', 'error')
        return redirect(url_for('user.dashboard'))


@user_bp.route('/supplier/<supplier_id>')
@login_required
def view_supplier(supplier_id):
    """View supplier profile and their materials"""
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.find_suppliers'))
    
    try:
        supplier_doc = db.collection('suppliers').document(supplier_id).get()
        
        if not supplier_doc.exists:
            flash('Supplier not found', 'error')
            return redirect(url_for('user.find_suppliers'))
        
        supplier_data = supplier_doc.to_dict()
        supplier_data['id'] = supplier_id
        
        # Get materials offered by this supplier
        materials_ref = db.collection('materials').where('supplier_id', '==', supplier_id).stream()
        materials = []
        
        for doc in materials_ref:
            material_data = doc.to_dict()
            material_data['id'] = doc.id
            materials.append(material_data)
        
        return render_template('user/supplier_profile.html', supplier=supplier_data, materials=materials)
        
    except Exception as e:
        flash(f'Error loading supplier: {str(e)}', 'error')
        return redirect(url_for('user.find_suppliers'))


@user_bp.route('/project/<project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    """Edit an existing project"""
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
        
        # Check ownership
        if project_data.get('user_id') != current_user.id:
            flash('Access denied', 'error')
            return redirect(url_for('user.projects'))
        
        if request.method == 'POST':
            from services.calculation_service import calculate_materials_and_cost
            
            square_feet = float(request.form.get('square_feet'))
            rooms = int(request.form.get('rooms'))
            floors = int(request.form.get('floors'))
            bathrooms = int(request.form.get('bathrooms', 2))
            budget_range = request.form.get('budget_range')
            
            # Recalculate estimation
            estimation = calculate_materials_and_cost(
                square_feet, rooms, floors, bathrooms, budget_range
            )
            
            # Update project data
            updated_data = {
                'title': request.form.get('title'),
                'square_feet': square_feet,
                'rooms': rooms,
                'floors': floors,
                'bathrooms': bathrooms,
                'location': request.form.get('location'),
                'property_type': request.form.get('property_type', 'residential'),
                'budget_range': budget_range,
                'description': request.form.get('description'),
                'estimation': estimation,
                'updated_at': datetime.now()
            }
            
            db.collection('projects').document(project_id).update(updated_data)
            flash('Project updated successfully!', 'success')
            return redirect(url_for('user.view_project', project_id=project_id))
        
        # GET request - show edit form
        project_data['id'] = project_id
        return render_template('user/edit_project.html', project=project_data)
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('user.projects'))


@user_bp.route('/materials/browse')
@login_required
def browse_materials():
    """Browse available materials from suppliers"""
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.dashboard'))
    
    try:
        # Get all materials from all suppliers
        materials_ref = db.collection('materials').stream()
        materials = []
        
        for doc in materials_ref:
            material_data = doc.to_dict()
            material_data['id'] = doc.id
            
            # Get supplier info
            supplier_id = material_data.get('supplier_id')
            if supplier_id:
                supplier_doc = db.collection('suppliers').document(supplier_id).get()
                if supplier_doc.exists:
                    supplier_data = supplier_doc.to_dict()
                    material_data['supplier_name'] = supplier_data.get('company_name') or supplier_data.get('name')
                    material_data['supplier_rating'] = supplier_data.get('rating', 0.0)
            
            materials.append(material_data)
        
        return render_template('user/browse_materials.html', materials=materials)
        
    except Exception as e:
        flash(f'Error loading materials: {str(e)}', 'error')
        return redirect(url_for('user.dashboard'))


@user_bp.route('/project/<project_id>/order-materials')
@login_required
def order_materials(project_id):
    """Order materials for a specific project"""
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.projects'))
    
    try:
        # Get project
        project_doc = db.collection('projects').document(project_id).get()
        
        if not project_doc.exists:
            flash('Project not found', 'error')
            return redirect(url_for('user.projects'))
        
        project_data = project_doc.to_dict()
        
        # Check ownership
        if project_data.get('user_id') != current_user.id:
            flash('Access denied', 'error')
            return redirect(url_for('user.projects'))
        
        project_data['id'] = project_id
        
        # Get all materials
        materials_ref = db.collection('materials').stream()
        materials = []
        
        for doc in materials_ref:
            material_data = doc.to_dict()
            material_data['id'] = doc.id
            
            # Get supplier info
            supplier_id = material_data.get('supplier_id')
            if supplier_id:
                supplier_doc = db.collection('suppliers').document(supplier_id).get()
                if supplier_doc.exists:
                    supplier_data = supplier_doc.to_dict()
                    material_data['supplier_name'] = supplier_data.get('company_name') or supplier_data.get('name')
            
            materials.append(material_data)
        
        # Get project's estimated materials
        estimation = project_data.get('estimation', {})
        estimated_materials = estimation.get('materials', {})
        
        return render_template('user/order_materials.html', 
                             project=project_data, 
                             materials=materials,
                             estimated_materials=estimated_materials)
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('user.projects'))


@user_bp.route('/order/create', methods=['POST'])
@login_required
def create_order():
    """Create a material order"""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        project_id = request.form.get('project_id')
        material_ids = request.form.getlist('material_ids[]')
        quantities = request.form.getlist('quantities[]')
        
        print("=" * 50)
        print("ORDER CREATION DEBUG")
        print(f"Project ID: {project_id}")
        print(f"Material IDs: {material_ids}")
        print(f"Quantities: {quantities}")
        print("=" * 50)
        
        if not material_ids or not quantities:
            return jsonify({'success': False, 'message': 'No materials selected'}), 400
        
        # Calculate total
        total_cost = 0
        order_items = []
        supplier_ids = set()
        
        for i, material_id in enumerate(material_ids):
            material_doc = db.collection('materials').document(material_id).get()
            if material_doc.exists:
                material_data = material_doc.to_dict()
                quantity = int(quantities[i])
                item_cost = material_data.get('price', 0) * quantity
                
                order_items.append({
                    'material_id': material_id,
                    'material_name': material_data.get('name'),
                    'quantity': quantity,
                    'unit': material_data.get('unit'),
                    'price_per_unit': material_data.get('price'),
                    'total': item_cost,
                    'supplier_id': material_data.get('supplier_id')
                })
                
                total_cost += item_cost
                supplier_ids.add(material_data.get('supplier_id'))
        
        print(f"Total order items: {len(order_items)}")
        print(f"Total cost: ₹{total_cost}")
        print(f"Supplier IDs: {supplier_ids}")
        
        # Get project info
        project_doc = db.collection('projects').document(project_id).get()
        project_data = project_doc.to_dict() if project_doc.exists else {}
        
        # Create separate orders for each supplier
        created_orders = []
        for supplier_id in supplier_ids:
            if not supplier_id:
                print("⚠️ Skipping None supplier_id")
                continue
                
            supplier_items = [item for item in order_items if item.get('supplier_id') == supplier_id]
            supplier_total = sum(item.get('total', 0) for item in supplier_items)
            
            # Get supplier info
            supplier_doc = db.collection('suppliers').document(supplier_id).get()
            supplier_data = supplier_doc.to_dict() if supplier_doc.exists else {}
            
            supplier_order = {
                'user_id': current_user.id,
                'user_name': current_user.name,
                'user_email': current_user.email if hasattr(current_user, 'email') else '',
                'project_id': project_id,
                'project_title': project_data.get('title', 'Untitled Project'),
                'supplier_id': supplier_id,
                'supplier_name': supplier_data.get('company_name') or supplier_data.get('name', 'Supplier'),
                'items': supplier_items,
                'total': supplier_total,
                'status': 'pending',
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            
            print(f"Creating order for supplier: {supplier_data.get('company_name', 'Unknown')}")
            print(f"Items: {len(supplier_items)}, Total: ₹{supplier_total}")
            
            order_ref = db.collection('orders').add(supplier_order)
            created_orders.append(order_ref[1].id)
            print(f"✅ Order created with ID: {order_ref[1].id}")
        
        print(f"✅ Total {len(created_orders)} order(s) created successfully!")
        print("=" * 50)
        
        return jsonify({
            'success': True, 
            'message': f'Order placed successfully! {len(created_orders)} order(s) created.',
            'order_ids': created_orders
        })
        
    except Exception as e:
        print(f"❌ Error creating order: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500
@user_bp.route('/my-orders')
@login_required
def my_orders():
    """View all material orders placed by the user"""
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.dashboard'))
    
    try:
        # Get all orders for this user
        orders_ref = db.collection('orders').where('user_id', '==', current_user.id).stream()
        orders = []
        
        for doc in orders_ref:
            order_data = doc.to_dict()
            order_data['id'] = doc.id
            
            # Convert items to order_items to avoid conflict with dict.items() method
            if 'items' in order_data:
                order_data['order_items'] = order_data['items']
            
            orders.append(order_data)
        
        # Sort by created_at descending
        orders.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)
        
        # Calculate statistics
        stats = {
            'total': len(orders),
            'pending': len([o for o in orders if o.get('status') == 'pending']),
            'processing': len([o for o in orders if o.get('status') == 'processing']),
            'completed': len([o for o in orders if o.get('status') == 'completed']),
            'cancelled': len([o for o in orders if o.get('status') == 'cancelled']),
            'total_spent': sum(o.get('total', 0) for o in orders if o.get('status') == 'completed')
        }
        
        return render_template('user/my_orders.html', orders=orders, stats=stats)
        
    except Exception as e:
        flash(f'Error loading orders: {str(e)}', 'error')
        return redirect(url_for('user.dashboard'))

@user_bp.route('/supplier/<supplier_id>/contact')
@login_required
def contact_supplier(supplier_id):
    """Show contact information for a supplier"""
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.find_suppliers'))
    
    try:
        supplier_doc = db.collection('suppliers').document(supplier_id).get()
        
        if not supplier_doc.exists:
            flash('Supplier not found', 'error')
            return redirect(url_for('user.find_suppliers'))
        
        supplier_data = supplier_doc.to_dict()
        supplier_data['id'] = supplier_id
        
        return render_template('user/supplier_contact.html', supplier=supplier_data)
        
    except Exception as e:
        flash(f'Error loading supplier contact: {str(e)}', 'error')
        return redirect(url_for('user.find_suppliers'))

@user_bp.route('/supplier/<supplier_id>/send-message', methods=['POST'])
@login_required
def send_message_to_supplier(supplier_id):
    """Send a message to a supplier"""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        print("=" * 80)
        print("📤 USER SENDING MESSAGE TO SUPPLIER")
        print(f"User ID: {current_user.id}")
        print(f"User Name: {current_user.name}")
        print(f"Target Supplier ID: {supplier_id}")
        print("=" * 80)
        
        # Get form data with validation
        subject = request.form.get('subject', '').strip()
        message_content = request.form.get('message', '').strip()
        
        print(f"Subject: {repr(subject)}")
        print(f"Message: {repr(message_content)}")
        
        # Validate - Reject empty values
        if not subject or not message_content:
            print("❌ Validation failed: Empty fields")
            return jsonify({
                'success': False,
                'message': 'Please fill in all required fields'
            }), 400
        
        # Get supplier info
        supplier_ref = db.collection('suppliers').document(supplier_id)
        supplier_doc = supplier_ref.get()
        
        if not supplier_doc.exists:
            print(f"❌ Supplier not found: {supplier_id}")
            return jsonify({'success': False, 'message': 'Supplier not found'}), 404
        
        supplier_data = supplier_doc.to_dict()
        supplier_name = supplier_data.get('company_name') or supplier_data.get('name', 'Unknown Supplier')
        
        print(f"Supplier Name: {supplier_name}")
        
        # Create message with guaranteed non-null values
        message_data = {
            'supplier_id': supplier_id,
            'supplier_name': supplier_name,
            'user_id': current_user.id,
            'sender_name': current_user.name,
            'sender_email': current_user.email if hasattr(current_user, 'email') else '',
            'sender_phone': current_user.phone if hasattr(current_user, 'phone') else '',
            'subject': subject,
            'message': message_content,
            'type': 'inquiry',
            'read': False,
            'created_at': datetime.now()
        }
        
        print("\n📝 Message data to be saved:")
        for key, value in message_data.items():
            if key != 'created_at':
                print(f"  {key}: {repr(value)}")
        
        # Save to Firebase
        doc_ref = db.collection('messages').add(message_data)
        message_id = doc_ref[1].id
        
        print(f"\n✅ Message saved successfully!")
        print(f"Message ID: {message_id}")
        print("=" * 80)
        
        return jsonify({
            'success': True,
            'message': 'Message sent successfully! The supplier will respond soon.'
        })
        
    except Exception as e:
        print(f"❌ ERROR sending message: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        return jsonify({'success': False, 'message': str(e)}), 500


@user_bp.route('/supplier/<supplier_id>/request-quote', methods=['POST'])
@login_required
def request_quote_from_supplier(supplier_id):
    """Request a quote from a supplier"""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        print("=" * 80)
        print("💰 USER REQUESTING QUOTE FROM SUPPLIER")
        print(f"User ID: {current_user.id}")
        print(f"User Name: {current_user.name}")
        print(f"Target Supplier ID: {supplier_id}")
        print("=" * 80)
        
        # Get form data with validation
        project_type = request.form.get('project_type', '').strip()
        material_type = request.form.get('material_type', '').strip()
        quantity = request.form.get('quantity', '').strip()
        unit = request.form.get('unit', '').strip()
        project_details = request.form.get('project_details', '').strip()
        
        print(f"Project Type: {repr(project_type)}")
        print(f"Material Type: {repr(material_type)}")
        print(f"Quantity: {repr(quantity)}")
        print(f"Unit: {repr(unit)}")
        print(f"Details: {repr(project_details)}")
        
        # Validate
        if not all([project_type, material_type, quantity, unit, project_details]):
            print("❌ Validation failed: Missing fields")
            return jsonify({
                'success': False,
                'message': 'Please fill in all required fields'
            }), 400
        
        # Get supplier info
        supplier_ref = db.collection('suppliers').document(supplier_id)
        supplier_doc = supplier_ref.get()
        
        if not supplier_doc.exists:
            print(f"❌ Supplier not found: {supplier_id}")
            return jsonify({'success': False, 'message': 'Supplier not found'}), 404
        
        supplier_data = supplier_doc.to_dict()
        supplier_name = supplier_data.get('company_name') or supplier_data.get('name', 'Unknown Supplier')
        
        print(f"Supplier Name: {supplier_name}")
        
        # Create quote request with guaranteed non-null values
        quote_data = {
            'supplier_id': supplier_id,
            'supplier_name': supplier_name,
            'user_id': current_user.id,
            'sender_name': current_user.name,
            'sender_email': current_user.email if hasattr(current_user, 'email') else '',
            'sender_phone': current_user.phone if hasattr(current_user, 'phone') else '',
            'subject': f'Quote Request: {material_type}',
            'message': project_details,
            'type': 'quote_request',
            'project_type': project_type,
            'material_type': material_type,
            'quantity': quantity,
            'unit': unit,
            'project_details': project_details,
            'read': False,
            'created_at': datetime.now()
        }
        
        print("\n📝 Quote request data to be saved:")
        for key, value in quote_data.items():
            if key != 'created_at':
                print(f"  {key}: {repr(value)}")
        
        # Save to Firebase
        doc_ref = db.collection('messages').add(quote_data)
        quote_id = doc_ref[1].id
        
        print(f"\n✅ Quote request saved successfully!")
        print(f"Message ID: {quote_id}")
        print("=" * 80)
        
        return jsonify({
            'success': True,
            'message': 'Quote request sent successfully! The supplier will review it and contact you.'
        })
        
    except Exception as e:
        print(f"❌ ERROR sending quote request: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        return jsonify({'success': False, 'message': str(e)}), 500

@user_bp.route('/contractor/<contractor_id>/contact')
@login_required
def contact_contractor(contractor_id):
    """Show contact information for a contractor"""
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.find_contractor'))
    
    try:
        contractor_doc = db.collection('contractor').document(contractor_id).get()
        
        if not contractor_doc.exists:
            flash('contractor not found', 'error')
            return redirect(url_for('user.find_contractor'))
        
        contractor_data = contractor_doc.to_dict()
        contractor_data['id'] = contractor_id
        
        return render_template('user/contractor_contact.html', contractor=contractor_data)
        
    except Exception as e:
        flash(f'Error loading supplier contact: {str(e)}', 'error')
        return redirect(url_for('user.find_contractor'))

@user_bp.route('/contractor/<contractor_id>/send-message', methods=['POST'])
@login_required
def send_message_to_contractor(contractor_id):
    """Send a message to a contractor"""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        print("=" * 80)
        print("📤 USER SENDING MESSAGE TO CONTRACTOR")
        print(f"User ID: {current_user.id}")
        print(f"User Name: {current_user.name}")
        print(f"Target Contractor ID: {contractor_id}")
        print("=" * 80)
        
        # Get form data with validation
        subject = request.form.get('subject', '').strip()
        message_content = request.form.get('message', '').strip()
        
        print(f"Subject: {repr(subject)}")
        print(f"Message: {repr(message_content)}")
        
        # Validate - Reject empty values
        if not subject or not message_content:
            print("❌ Validation failed: Empty fields")
            return jsonify({
                'success': False,
                'message': 'Please fill in all required fields'
            }), 400
        
        # Get contractor info
        contractor_ref = db.collection('contractors').document(contractor_id)
        contractor_doc = contractor_ref.get()
        
        if not contractor_doc.exists:
            print(f"❌ Contractor not found: {contractor_id}")
            return jsonify({'success': False, 'message': 'Contractor not found'}), 404
        
        contractor_data = contractor_doc.to_dict()
        contractor_name = contractor_data.get('company_name') or contractor_data.get('name', 'Unknown Contractor')
        
        print(f"Contractor Name: {contractor_name}")
        
        # Create message with guaranteed non-null values
        message_data = {
            'contractor_id': contractor_id,
            'contractor_name': contractor_name,
            'user_id': current_user.id,
            'sender_name': current_user.name,
            'sender_email': current_user.email if hasattr(current_user, 'email') else '',
            'sender_phone': current_user.phone if hasattr(current_user, 'phone') else '',
            'subject': subject,
            'message': message_content,
            'type': 'inquiry',
            'read': False,
            'created_at': datetime.now()
        }
        
        print("\n📝 Message data to be saved:")
        for key, value in message_data.items():
            if key != 'created_at':
                print(f"  {key}: {repr(value)}")
        
        # Save to Firebase
        doc_ref = db.collection('messages').add(message_data)
        message_id = doc_ref[1].id
        
        print(f"\n✅ Message saved successfully!")
        print(f"Message ID: {message_id}")
        print("=" * 80)
        
        return jsonify({
            'success': True,
            'message': 'Message sent successfully! The contractor will respond soon.'
        })
        
    except Exception as e:
        print(f"❌ ERROR sending message: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        return jsonify({'success': False, 'message': str(e)}), 500


@user_bp.route('/contractor/<contractor_id>/request-quote', methods=['POST'])
@login_required
def request_quote_from_contractor(contractor_id):
    """Request a quote from a contractor"""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        print("=" * 80)
        print("💰 USER REQUESTING QUOTE FROM CONTRACTOR")
        print(f"User ID: {current_user.id}")
        print(f"User Name: {current_user.name}")
        print(f"Target Contractor ID: {contractor_id}")
        print("=" * 80)
        
        # Get form data with validation
        project_type = request.form.get('project_type', '').strip()
        project_area = request.form.get('project_area', '').strip()
        project_location = request.form.get('project_location', '').strip()
        project_budget = request.form.get('project_budget', '').strip()
        project_details = request.form.get('project_details', '').strip()
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        
        print(f"Project Type: {repr(project_type)}")
        print(f"Project Area: {repr(project_area)}")
        print(f"Location: {repr(project_location)}")
        print(f"Budget: {repr(project_budget)}")
        
        # Validate
        if not all([project_type, project_area, project_location, project_budget, project_details, name, phone, email]):
            print("❌ Validation failed: Missing fields")
            return jsonify({
                'success': False,
                'message': 'Please fill in all required fields'
            }), 400
        
        # Get contractor info
        contractor_ref = db.collection('contractors').document(contractor_id)
        contractor_doc = contractor_ref.get()
        
        if not contractor_doc.exists:
            print(f"❌ Contractor not found: {contractor_id}")
            return jsonify({'success': False, 'message': 'Contractor not found'}), 404
        
        contractor_data = contractor_doc.to_dict()
        contractor_name = contractor_data.get('company_name') or contractor_data.get('name', 'Unknown Contractor')
        
        print(f"Contractor Name: {contractor_name}")
        
        # Create quote request with guaranteed non-null values
        quote_data = {
            'contractor_id': contractor_id,
            'contractor_name': contractor_name,
            'user_id': current_user.id,
            'sender_name': name,
            'sender_email': email,
            'sender_phone': phone,
            'subject': f'Quote Request: {project_type}',
            'message': project_details,
            'type': 'quote_request',
            'project_type': project_type,
            'project_area': project_area,
            'project_location': project_location,
            'project_budget': project_budget,
            'project_details': project_details,
            'read': False,
            'created_at': datetime.now()
        }
        
        print("\n📝 Quote request data to be saved:")
        for key, value in quote_data.items():
            if key != 'created_at':
                print(f"  {key}: {repr(value)}")
        
        # Save to Firebase
        doc_ref = db.collection('messages').add(quote_data)
        quote_id = doc_ref[1].id
        
        print(f"\n✅ Quote request saved successfully!")
        print(f"Message ID: {quote_id}")
        print("=" * 80)
        
        return jsonify({
            'success': True,
            'message': 'Quote request sent successfully! The contractor will review it and contact you.'
        })
        
    except Exception as e:
        print(f"❌ ERROR sending quote request: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        return jsonify({'success': False, 'message': str(e)}), 500