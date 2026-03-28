from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from firebase_admin import firestore
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os

def debug_user_info(action=""):
    """Debug helper to print current user information"""
    print("=" * 80)
    print(f"🔍 USER DEBUG - {action}")
    print(f"User ID: {current_user.id}")
    print(f"User Name: {current_user.name if hasattr(current_user, 'name') else 'N/A'}")
    print(f"User Email: {current_user.email if hasattr(current_user, 'email') else 'N/A'}")
    print(f"Is Authenticated: {current_user.is_authenticated}")
    print(f"Is Active: {current_user.is_active if hasattr(current_user, 'is_active') else 'N/A'}")
    print("=" * 80)

user_bp = Blueprint('user', __name__)
db = firestore.client()

def get_db():
    """Get database instance"""
    try:
        return firestore.client()
    except Exception as e:
        print(f"Error getting database: {e}")
        return None

# ── REPLACE your dashboard() function in user_routes.py with this ────────────
# The old version was missing user_profile_picture — Jinja errors crashed nav links silently.

@user_bp.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('index'))

    projects_ref = db.collection('projects').where('user_id', '==', current_user.id).stream()
    projects = []
    for doc in projects_ref:
        project_data = doc.to_dict()
        project_data['id'] = doc.id
        projects.append(project_data)

    estimates_ref = db.collection('estimates').where('user_id', '==', current_user.id).limit(5).stream()
    estimates = [dict(**doc.to_dict(), id=doc.id) for doc in estimates_ref]

    orders_ref = db.collection('orders').where('user_id', '==', current_user.id).limit(5).stream()
    orders = [dict(**doc.to_dict(), id=doc.id) for doc in orders_ref]

    stats = {
        'total_projects':  len(projects),
        'active_projects': len([p for p in projects if p.get('status') == 'active']),
        'total_estimates': len(estimates),
        'total_orders':    len(orders),
    }

    # ✅ FIXED: pass user_profile_picture so navbar doesn't crash
    user_profile_picture = None
    try:
        user_doc = db.collection('users').document(current_user.id).get()
        if user_doc.exists:
            user_profile_picture = user_doc.to_dict().get('profile_picture')
    except Exception:
        pass

    return render_template('user/dashboard.html',
                           projects=projects[:5],
                           estimates=estimates,
                           orders=orders,
                           stats=stats,
                           user_profile_picture=user_profile_picture)

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
    
    debug_user_info("LIST PROJECTS")
    
    projects_ref = db.collection('projects').where('user_id', '==', current_user.id).stream()
    projects = []
    for doc in projects_ref:
        project_data = doc.to_dict()
        project_data['id'] = doc.id
        print(f"📋 Found project: {project_data.get('title')} (ID: {doc.id})")
        projects.append(project_data)
    
    print(f"✅ Total projects found: {len(projects)}")
    print("=" * 80)
    
    return render_template('user/my_projects.html', projects=projects)

# ─────────────────────────────────────────────────────────────────────────────
#  REPLACE the create_project route in routes/user_routes.py with this block.
#  The only change is passing request.form to calculate_materials_and_cost so
#  the new detailed calculator can read all the extra HTML form fields.
# ─────────────────────────────────────────────────────────────────────────────

@user_bp.route('/create-project', methods=['GET', 'POST'])
@login_required
def create_project():
    """Create new construction project"""
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.dashboard'))

    # Pass user profile picture to template (used by navbar)
    user_profile_picture = None
    try:
        user_doc = db.collection('users').document(current_user.id).get()
        if user_doc.exists:
            user_profile_picture = user_doc.to_dict().get('profile_picture')
    except Exception:
        pass

    if request.method == 'POST':
        from services.calculation_service import calculate_materials_and_cost

        # ── Core scalar fields ────────────────────────────────────────────────
        square_feet  = float(request.form.get('square_feet', 0) or 0)
        plot_area    = float(request.form.get('plot_area', 0) or 0)
        prop_type    = request.form.get('property_type', 'residential')
        budget_range = request.form.get('budget_range', 'medium')

        # Rooms / floors / bathrooms differ by property type
        if prop_type == 'apartment':
            rooms     = int(request.form.get('apt_total_units') or 0)
            floors    = int(request.form.get('apt_total_floors') or 1)
            bathrooms = max(1, (int(request.form.get('apt_1bhk_count') or 0)
                              + int(request.form.get('apt_2bhk_count') or 0) * 2
                              + int(request.form.get('apt_3bhk_count') or 0) * 3)
                          // max(rooms, 1))
        else:
            rooms     = int(request.form.get('rooms') or 1)
            floors    = int(request.form.get('floors') or 1)
            bathrooms = int(request.form.get('bathrooms') or 2)

        # ── Full estimation with all form fields ──────────────────────────────
        estimation = calculate_materials_and_cost(
            square_feet  = square_feet,
            rooms        = rooms,
            floors       = floors,
            bathrooms    = bathrooms,
            budget_range = budget_range,
            form         = request.form,
        )

        project_data = {
            # ── Core ─────────────────────────────────────────────────────────
            'user_id':        current_user.id,
            'title':          request.form.get('title'),
            'square_feet':    square_feet,
            'plot_area':      plot_area,
            'rooms':          rooms,
            'floors':         floors,
            'bathrooms':      bathrooms,
            'location':       request.form.get('location'),
            'property_type':  prop_type,
            'budget_range':   budget_range,
            'estimate_scope': request.form.get('estimate_scope', 'material_only'),
            'description':    request.form.get('description'),
            'status':         'planning',
            'created_at':     datetime.now(),
            'estimation':     estimation,

            # ── Location sub-fields ───────────────────────────────────────────
            'location_state':    request.form.get('location_state', ''),
            'location_district': request.form.get('location_district', ''),
            'location_place':    request.form.get('location_place', ''),
            'location_pin':      request.form.get('location_pin', ''),
            'location_address':  request.form.get('location_address', ''),

            # ── Structural ────────────────────────────────────────────────────
            'structure_type':     request.form.get('structure_type', ''),
            'concrete_grade':     request.form.get('concrete_grade', ''),
            'steel_grade':        request.form.get('steel_grade', ''),
            'slab_thickness':     request.form.get('slab_thickness', ''),
            'ceiling_height':     request.form.get('ceiling_height', ''),
            'soil_condition':     request.form.get('soil_condition', ''),
            'foundation_type':    request.form.get('foundation_type', ''),
            'foundation_depth':   request.form.get('foundation_depth', ''),
            'anti_termite':       request.form.get('anti_termite', ''),
            'staircase_type':     request.form.get('staircase_type', ''),
            'roof_waterproofing': request.form.get('roof_waterproofing', ''),

            # ── Masonry & Openings ────────────────────────────────────────────
            'wall_material':         request.form.get('wall_material', ''),
            'wall_thickness':        request.form.get('wall_thickness', ''),
            'inner_wall_thickness':  request.form.get('inner_wall_thickness', ''),
            'num_doors':             request.form.get('num_doors', ''),
            'num_windows':           request.form.get('num_windows', ''),
            'plaster_type':          request.form.get('plaster_type', ''),
            'external_plaster_type': request.form.get('external_plaster_type', ''),
            'door_material':         request.form.get('door_material', ''),
            'window_material':       request.form.get('window_material', ''),

            # ── Finishing & Interiors ─────────────────────────────────────────
            'flooring_type':           request.form.get('flooring_type', ''),
            'bathroom_wall_tile':      request.form.get('bathroom_wall_tile', ''),
            'internal_paint_quality':  request.form.get('internal_paint_quality', ''),
            'external_paint_quality':  request.form.get('external_paint_quality', ''),
            'false_ceiling_yn':        request.form.get('false_ceiling_yn', 'no'),
            'kitchen_type':            request.form.get('kitchen_type', ''),
            'kitchen_platform_length': request.form.get('kitchen_platform_length', ''),
            'kitchen_platform_stone':  request.form.get('kitchen_platform_stone', ''),

            # ── Plumbing & Sanitary ───────────────────────────────────────────
            'pipe_material':  request.form.get('pipe_material', ''),
            'num_taps':       request.form.get('num_taps', ''),
            'num_showers':    request.form.get('num_showers', ''),
            'num_geysers':    request.form.get('num_geysers', ''),
            'sanitary_grade': request.form.get('sanitary_grade', ''),

            # ── Electrical ────────────────────────────────────────────────────
            'num_switchboards': request.form.get('num_switchboards', ''),
            'num_ac_points':    request.form.get('num_ac_points', ''),
            'wiring_type':      request.form.get('wiring_type', ''),
            'inverter_wiring':  request.form.get('inverter_wiring', ''),
            'earthing_system':  request.form.get('earthing_system', ''),

            # ── External Add-ons ──────────────────────────────────────────────
            'car_porch_size':         request.form.get('car_porch_size', ''),
            'car_porch_sqft':         request.form.get('car_porch_sqft', ''),
            'garden_sqft':            request.form.get('garden_sqft', ''),
            'boundary_rft':           request.form.get('boundary_rft', ''),
            'boundary_finish':        request.form.get('boundary_finish', ''),
            'sump_capacity':          request.form.get('sump_capacity', ''),
            'overhead_tank_capacity': request.form.get('overhead_tank_capacity', ''),

            # ── Villa-specific ────────────────────────────────────────────────
            'villa_roof_type':            request.form.get('villa_roof_type', ''),
            'villa_ceiling_height':       request.form.get('villa_ceiling_height', ''),
            'villa_staircase':            request.form.get('villa_staircase', ''),
            'villa_concrete_grade':       request.form.get('villa_concrete_grade', ''),
            'villa_steel_grade':          request.form.get('villa_steel_grade', ''),
            'villa_slab_thickness':       request.form.get('villa_slab_thickness', ''),
            'villa_soil_condition':       request.form.get('villa_soil_condition', ''),
            'villa_foundation_type':      request.form.get('villa_foundation_type', ''),
            'villa_foundation_depth':     request.form.get('villa_foundation_depth', ''),
            'villa_anti_termite':         request.form.get('villa_anti_termite', ''),
            'villa_roof_waterproofing':   request.form.get('villa_roof_waterproofing', ''),
            'villa_wall_material':        request.form.get('villa_wall_material', ''),
            'villa_wall_thickness':       request.form.get('villa_wall_thickness', ''),
            'villa_inner_wall_thickness': request.form.get('villa_inner_wall_thickness', ''),
            'villa_rooms':                request.form.get('villa_rooms', ''),
            'villa_bathrooms':            request.form.get('villa_bathrooms', ''),
            'villa_floors':               request.form.get('villa_floors', ''),
            'villa_num_doors':            request.form.get('villa_num_doors', ''),
            'villa_num_windows':          request.form.get('villa_num_windows', ''),
            'villa_door_material':        request.form.get('villa_door_material', ''),
            'villa_window_material':      request.form.get('villa_window_material', ''),
            'villa_plaster_type':         request.form.get('villa_plaster_type', ''),
            'villa_external_plaster_type':request.form.get('villa_external_plaster_type', ''),
            'villa_flooring_grade':       request.form.get('villa_flooring_grade', ''),
            'villa_flooring_coverage':    request.form.get('villa_flooring_coverage', ''),
            'villa_internal_paint':       request.form.get('villa_internal_paint', ''),
            'villa_external_paint':       request.form.get('villa_external_paint', ''),
            'villa_false_ceiling':        request.form.get('villa_false_ceiling', 'no'),
            'villa_cladding':             request.form.get('villa_cladding', ''),
            'villa_bathroom_wall_tile':   request.form.get('villa_bathroom_wall_tile', ''),
            'villa_pipe_material':        request.form.get('villa_pipe_material', ''),
            'villa_sanitary_grade':       request.form.get('villa_sanitary_grade', ''),
            'villa_num_taps':             request.form.get('villa_num_taps', ''),
            'villa_num_showers':          request.form.get('villa_num_showers', ''),
            'villa_num_geysers':          request.form.get('villa_num_geysers', ''),
            'villa_num_switchboards':     request.form.get('villa_num_switchboards', ''),
            'villa_num_ac_points':        request.form.get('villa_num_ac_points', ''),
            'villa_wiring_type':          request.form.get('villa_wiring_type', ''),
            'villa_inverter_wiring':      request.form.get('villa_inverter_wiring', ''),
            'villa_earthing_system':      request.form.get('villa_earthing_system', ''),
            'villa_boundary_rft':         request.form.get('villa_boundary_rft', ''),
            'villa_boundary_height':      request.form.get('villa_boundary_height', ''),
            'villa_boundary_finish':      request.form.get('villa_boundary_finish', ''),
            'villa_gate_type':            request.form.get('villa_gate_type', ''),
            'villa_garden_sqft':          request.form.get('villa_garden_sqft', ''),
            'villa_landscaping_grade':    request.form.get('villa_landscaping_grade', ''),
            'villa_driveway_sqft':        request.form.get('villa_driveway_sqft', ''),
            'villa_driveway_finish':      request.form.get('villa_driveway_finish', ''),
            'villa_car_porch_size':       request.form.get('villa_car_porch_size', ''),
            'villa_car_porch_sqft':       request.form.get('villa_car_porch_sqft', ''),
            'villa_car_porch_style':      request.form.get('villa_car_porch_style', ''),
            'villa_porch_flooring':       request.form.get('villa_porch_flooring', ''),
            'pool_length':                request.form.get('pool_length', ''),
            'pool_width':                 request.form.get('pool_width', ''),
            'pool_depth':                 request.form.get('pool_depth', ''),
            'pool_finish':                request.form.get('pool_finish', ''),
            'pool_deck':                  request.form.get('pool_deck', ''),

            # ── Apartment-specific ────────────────────────────────────────────
            'apt_total_floors':       request.form.get('apt_total_floors', ''),
            'apt_total_units':        request.form.get('apt_total_units', ''),
            'apt_ceiling_height':     request.form.get('apt_ceiling_height', ''),
            'apt_common_area_pct':    request.form.get('apt_common_area_pct', ''),
            'apt_1bhk_count':         request.form.get('apt_1bhk_count', ''),
            'apt_1bhk_size':          request.form.get('apt_1bhk_size', ''),
            'apt_2bhk_count':         request.form.get('apt_2bhk_count', ''),
            'apt_2bhk_size':          request.form.get('apt_2bhk_size', ''),
            'apt_3bhk_count':         request.form.get('apt_3bhk_count', ''),
            'apt_3bhk_size':          request.form.get('apt_3bhk_size', ''),
            'apt_concrete_grade':     request.form.get('apt_concrete_grade', ''),
            'apt_steel_grade':        request.form.get('apt_steel_grade', ''),
            'apt_slab_thickness':     request.form.get('apt_slab_thickness', ''),
            'apt_soil_condition':     request.form.get('apt_soil_condition', ''),
            'apt_foundation_type':    request.form.get('apt_foundation_type', ''),
            'apt_foundation_depth':   request.form.get('apt_foundation_depth', ''),
            'apt_roof_waterproofing': request.form.get('apt_roof_waterproofing', ''),
            'apt_anti_termite':       request.form.get('apt_anti_termite', ''),
            'apt_staircases':         request.form.get('apt_staircases', ''),
            'apt_staircase_type':     request.form.get('apt_staircase_type', ''),
            'apt_wall_material':      request.form.get('apt_wall_material', ''),
            'apt_wall_thickness':     request.form.get('apt_wall_thickness', ''),
            'apt_partition_material': request.form.get('apt_partition_material', ''),
            'apt_facade_type':        request.form.get('apt_facade_type', ''),
            'apt_external_plaster':   request.form.get('apt_external_plaster', ''),
            'apt_internal_plaster':   request.form.get('apt_internal_plaster', ''),
            'apt_external_paint':     request.form.get('apt_external_paint', ''),
            'apt_flooring_type':      request.form.get('apt_flooring_type', ''),
            'apt_bathroom_tile':      request.form.get('apt_bathroom_tile', ''),
            'apt_internal_paint':     request.form.get('apt_internal_paint', ''),
            'apt_false_ceiling':      request.form.get('apt_false_ceiling', 'none'),
            'apt_door_material':      request.form.get('apt_door_material', ''),
            'apt_window_material':    request.form.get('apt_window_material', ''),
            'apt_sanitary_grade':     request.form.get('apt_sanitary_grade', ''),
            'apt_kitchen_type':       request.form.get('apt_kitchen_type', ''),
            'apt_lifts':              request.form.get('apt_lifts', ''),
            'apt_lift_capacity':      request.form.get('apt_lift_capacity', ''),
            'apt_dg_backup':          request.form.get('apt_dg_backup', ''),
            'apt_dg_kva':             request.form.get('apt_dg_kva', ''),
            'apt_water_storage':      request.form.get('apt_water_storage', ''),
            'apt_fire_spec':          request.form.get('apt_fire_spec', ''),
            'apt_stp_type':           request.form.get('apt_stp_type', ''),
            'apt_security_level':     request.form.get('apt_security_level', ''),
            'apt_solar_kw':           request.form.get('apt_solar_kw', ''),
            'apt_parking_type':       request.form.get('apt_parking_type', ''),
            'apt_parking_slots':      request.form.get('apt_parking_slots', ''),
            'apt_basement_depth':     request.form.get('apt_basement_depth', ''),
            'apt_clubhouse':          request.form.get('apt_clubhouse', ''),
            'apt_pool':               request.form.get('apt_pool', ''),
            'apt_pool_finish':        request.form.get('apt_pool_finish', ''),
            'apt_external_dev_sqft':  request.form.get('apt_external_dev_sqft', ''),
            'apt_external_dev_grade': request.form.get('apt_external_dev_grade', ''),
            'apt_common_flooring':    request.form.get('apt_common_flooring', ''),
            'apt_common_paint':       request.form.get('apt_common_paint', ''),
            'apt_common_ceiling':     request.form.get('apt_common_ceiling', ''),
            'apt_lobby_wall_finish':  request.form.get('apt_lobby_wall_finish', ''),
        }

        doc_ref    = db.collection('projects').add(project_data)
        project_id = doc_ref[1].id
        project_data['id'] = project_id

        return render_template(
            'user/project_created.html',
            project    = project_data,
            estimation = estimation,
            project_id = project_id,
        )

    return render_template(
        'user/create_project.html',
        user_profile_picture = user_profile_picture,
    )

@user_bp.route('/project/<project_id>')
@login_required
def view_project(project_id):
    """View detailed project information with full estimation"""
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.projects'))
    
    try:
        debug_user_info(f"VIEW PROJECT: {project_id}")
        
        project_doc = db.collection('projects').document(project_id).get()
        
        if not project_doc.exists:
            print(f"❌ Project not found: {project_id}")
            flash('Project not found', 'error')
            return redirect(url_for('user.projects'))
        
        project_data = project_doc.to_dict()
        
        # Debug project ownership
        print(f"📋 Project user_id: {project_data.get('user_id')}")
        print(f"👤 Current user_id: {current_user.id}")
        print(f"🔐 Match: {project_data.get('user_id') == current_user.id}")
        
        # Verify ownership
        if project_data.get('user_id') != current_user.id:
            print(f"❌ Access denied - User ID mismatch")
            print(f"   Expected: {project_data.get('user_id')}")
            print(f"   Got: {current_user.id}")
            flash('Access denied', 'error')
            return redirect(url_for('user.projects'))
        
        project_data['id'] = project_id
        estimation = project_data.get('estimation', {})
        
        print(f"✅ Project loaded successfully: {project_data.get('title')}")
        print("=" * 80)
        
        return render_template(
            'user/project_detail.html',
            project=project_data,
            estimation=estimation
        )
                             
    except Exception as e:
        print(f"❌ Error loading project: {str(e)}")
        import traceback
        traceback.print_exc()
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
    """Create a material order — instant processing, no supplier accept required."""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
 
    try:
        project_id   = request.form.get('project_id')
        material_ids = request.form.getlist('material_ids[]')
        quantities   = request.form.getlist('quantities[]')
 
        # Delivery address fields (set on the order_materials page)
        delivery_address  = request.form.get('delivery_address', '').strip()
        delivery_district = request.form.get('delivery_district', '').strip()
        delivery_pin      = request.form.get('delivery_pin', '').strip()
        delivery_state    = request.form.get('delivery_state', '').strip()
        delivery_landmark = request.form.get('delivery_landmark', '').strip()
 
        print("=" * 60)
        print("ORDER CREATION — INSTANT CHECKOUT FLOW")
        print(f"Project ID : {project_id}")
        print(f"Materials  : {material_ids}")
        print(f"Quantities : {quantities}")
        print(f"Delivery   : {delivery_address}, {delivery_district}, {delivery_pin}")
        print("=" * 60)
 
        if not material_ids or not quantities:
            return jsonify({'success': False, 'message': 'No materials selected'}), 400
 
        # ── Build items & group by supplier ───────────────────────────────────
        total_cost   = 0
        order_items  = []
        supplier_ids = set()
 
        for i, material_id in enumerate(material_ids):
            material_doc = db.collection('materials').document(material_id).get()
            if not material_doc.exists:
                continue
            material_data = material_doc.to_dict()
            quantity      = max(1, int(quantities[i]))
            item_cost     = material_data.get('price', 0) * quantity
 
            order_items.append({
                'material_id':    material_id,
                'material_name':  material_data.get('name'),
                'quantity':       quantity,
                'unit':           material_data.get('unit'),
                'price_per_unit': material_data.get('price'),
                'total':          item_cost,
                'supplier_id':    material_data.get('supplier_id')
            })
            total_cost += item_cost
            supplier_ids.add(material_data.get('supplier_id'))
 
        # ── Get project info ──────────────────────────────────────────────────
        project_doc  = db.collection('projects').document(project_id).get()
        project_data = project_doc.to_dict() if project_doc.exists else {}
 
        # ── Create one order per supplier ─────────────────────────────────────
        created_order_ids = []
        for supplier_id in supplier_ids:
            if not supplier_id:
                continue
 
            supplier_items = [item for item in order_items
                              if item.get('supplier_id') == supplier_id]
            supplier_total = sum(item.get('total', 0) for item in supplier_items)
 
            supplier_doc  = db.collection('suppliers').document(supplier_id).get()
            supplier_data = supplier_doc.to_dict() if supplier_doc.exists else {}
 
            supplier_order = {
                # Core
                'user_id':        current_user.id,
                'user_name':      current_user.name,
                'user_email':     current_user.email if hasattr(current_user, 'email') else '',
                'project_id':     project_id,
                'project_title':  project_data.get('title', 'Untitled Project'),
                'supplier_id':    supplier_id,
                'supplier_name':  supplier_data.get('company_name') or supplier_data.get('name', 'Supplier'),
                'items':          supplier_items,
                'total':          supplier_total,
 
                # ── INSTANT PROCESSING — no accept step ──
                'status':         'processing',
 
                # Payment fields (filled later on checkout page)
                'payment_status': 'pending',
                'payment_method': None,
                'receipt_number': None,
 
                # Delivery address (captured from order_materials form)
                'delivery_address':  delivery_address,
                'delivery_district': delivery_district,
                'delivery_pin':      delivery_pin,
                'delivery_state':    delivery_state,
                'delivery_landmark': delivery_landmark,
 
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
 
            order_ref = db.collection('orders').add(supplier_order)
            new_id    = order_ref[1].id
            created_order_ids.append(new_id)
            print(f"✅ Order created instantly: {new_id} (supplier: {supplier_data.get('company_name','?')})")
 
        print(f"✅ {len(created_order_ids)} order(s) created — redirecting to checkout")
        print("=" * 60)
 
        # ── Redirect to checkout ──────────────────────────────────────────────
        # If single supplier → go straight to checkout for that order.
        # If multiple suppliers → go to my_orders where each order has a
        #   "Confirm Payment" button linking to its own checkout page.
        if len(created_order_ids) == 1:
            checkout_url = url_for('payment.checkout', order_id=created_order_ids[0])
        else:
            checkout_url = url_for('user.my_orders')
 
        return jsonify({
            'success':     True,
            'message':     f'{len(created_order_ids)} order(s) placed! Proceeding to payment…',
            'order_ids':   created_order_ids,
            'redirect_url': checkout_url   # ← frontend should redirect here
        })
 
    except Exception as e:
        print(f"❌ Error creating order: {str(e)}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500
    
@user_bp.route('/my-orders')
@login_required
def my_orders():
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.dashboard'))
    
    try:
        orders_ref = db.collection('orders').where('user_id', '==', current_user.id).stream()
        orders = []
        
        for doc in orders_ref:
            order_data = doc.to_dict()
            order_data['id'] = doc.id
            if 'items' in order_data:
                order_data['order_items'] = order_data['items']
            orders.append(order_data)
        
        orders.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)
        
        stats = {
            'total': len(orders),
            'pending': len([o for o in orders if o.get('status') == 'pending']),
            'processing': len([o for o in orders if o.get('status') == 'processing']),
            'completed': len([o for o in orders if o.get('status') == 'completed']),
            'cancelled': len([o for o in orders if o.get('status') == 'cancelled']),
            'total_spent': sum(o.get('total', 0) for o in orders if o.get('status') == 'completed')
        }

        # ✅ FIX: fetch profile picture just like dashboard() does
        user_profile_picture = None
        try:
            user_doc = db.collection('users').document(current_user.id).get()
            if user_doc.exists:
                user_profile_picture = user_doc.to_dict().get('profile_picture')
        except Exception:
            pass
        
        return render_template('user/my_orders.html',
                               orders=orders,
                               stats=stats,
                               user_profile_picture=user_profile_picture)  # ✅ added
        
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
        return redirect(url_for('user.find_contractors'))
    
    try:
        contractor_doc = db.collection('contractors').document(contractor_id).get()
        
        if not contractor_doc.exists:
            flash('Contractor not found', 'error')
            return redirect(url_for('user.find_contractors'))
        
        contractor_data = contractor_doc.to_dict()
        contractor_data['id'] = contractor_id
        
        return render_template('user/contractor_contact.html', contractor=contractor_data)
        
    except Exception as e:
        flash(f'Error loading contractor contact: {str(e)}', 'error')
        return redirect(url_for('user.find_contractors'))


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
    
@user_bp.route('/project-delete/<project_id>', methods=['POST', 'DELETE'])
@login_required
def delete_project(project_id):
    """Delete a project"""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        debug_user_info(f"DELETE PROJECT: {project_id}")
        
        # Get project to verify ownership
        project_doc = db.collection('projects').document(project_id).get()
        
        if not project_doc.exists:
            print(f"❌ Project not found: {project_id}")
            return jsonify({'success': False, 'message': 'Project not found'}), 404
        
        project_data = project_doc.to_dict()
        
        # Debug ownership check
        print(f"📋 Project user_id: {project_data.get('user_id')}")
        print(f"👤 Current user_id: {current_user.id}")
        print(f"🔐 Match: {project_data.get('user_id') == current_user.id}")
        
        # Check ownership
        if project_data.get('user_id') != current_user.id:
            print(f"❌ Access denied - User ID mismatch")
            print(f"   Expected: {project_data.get('user_id')}")
            print(f"   Got: {current_user.id}")
            return jsonify({'success': False, 'message': 'Access denied - You do not own this project'}), 403
        
        # Delete related bids first (if any)
        try:
            bids_ref = db.collection('bids').where('project_id', '==', project_id).stream()
            deleted_bids = 0
            for bid in bids_ref:
                db.collection('bids').document(bid.id).delete()
                deleted_bids += 1
            print(f"✅ Deleted {deleted_bids} related bids")
        except Exception as e:
            print(f"⚠️ Error deleting bids: {e}")
        
        # Delete related orders (if any)
        try:
            orders_ref = db.collection('orders').where('project_id', '==', project_id).stream()
            deleted_orders = 0
            for order in orders_ref:
                db.collection('orders').document(order.id).delete()
                deleted_orders += 1
            print(f"✅ Deleted {deleted_orders} related orders")
        except Exception as e:
            print(f"⚠️ Error deleting orders: {e}")
        
        # Delete the project
        db.collection('projects').document(project_id).delete()
        
        print(f"✅ Project '{project_data.get('title')}' deleted successfully!")
        print("=" * 80)
        
        return jsonify({
            'success': True,
            'message': 'Project deleted successfully!'
        })
        
    except Exception as e:
        print(f"❌ ERROR deleting project: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        return jsonify({'success': False, 'message': str(e)}), 500

# ======================== MESSAGING ROUTES ========================
# Add these routes to routes/user_routes.py

@user_bp.route('/messages')
@login_required
def messages():
    """View all message conversations (chat style)"""
    return render_template('user/messages.html')


@user_bp.route('/messages/conversations')
@login_required
def messages_conversations():
    """Get all conversations for the user"""
    db = get_db()
    if not db:
        return jsonify({'conversations': []})
    
    try:
        print("=" * 80)
        print("📨 LOADING CONVERSATIONS FOR USER")
        print(f"User ID: {current_user.id}")
        print("=" * 80)
        
        conversations = {}
        
        # Get ALL messages involving this user
        all_messages = db.collection('messages').stream()
        
        for doc in all_messages:
            msg = doc.to_dict()
            
            # Check if this message involves the current user
            contractor_id = msg.get('contractor_id')
            supplier_id = msg.get('supplier_id')
            msg_user_id = msg.get('user_id')
            sender_id = msg.get('sender_id')
            sender_type = msg.get('sender_type')
            
            # Skip messages that don't involve this user
            if msg_user_id != current_user.id and sender_id != current_user.id:
                continue
            
            # Process contractor conversations
            if contractor_id:
                conv_key = f"contractor_{contractor_id}"
                
                if conv_key not in conversations:
                    conversations[conv_key] = {
                        'id': contractor_id,
                        'sender_id': contractor_id,
                        'sender_type': 'contractor',
                        'sender_name': msg.get('contractor_name', 'Contractor'),
                        'sender_email': msg.get('contractor_email', ''),
                        'sender_phone': msg.get('contractor_phone', ''),
                        'last_message': msg.get('message', ''),
                        'last_message_time': msg.get('created_at', datetime.min),
                        'unread_count': 0
                    }
                
                # Update if this message is newer
                msg_time = msg.get('created_at', datetime.min)
                if msg_time > conversations[conv_key]['last_message_time']:
                    conversations[conv_key]['last_message'] = msg.get('message', '')
                    conversations[conv_key]['last_message_time'] = msg_time
                
                # Count unread (messages FROM contractor TO user that are unread)
                is_from_contractor = sender_type == 'contractor' and sender_id == contractor_id
                if is_from_contractor and not msg.get('read', False):
                    conversations[conv_key]['unread_count'] += 1
            
            # Process supplier conversations
            if supplier_id:
                conv_key = f"supplier_{supplier_id}"
                
                if conv_key not in conversations:
                    conversations[conv_key] = {
                        'id': supplier_id,
                        'sender_id': supplier_id,
                        'sender_type': 'supplier',
                        'sender_name': msg.get('supplier_name', 'Supplier'),
                        'sender_email': msg.get('supplier_email', ''),
                        'sender_phone': msg.get('supplier_phone', ''),
                        'last_message': msg.get('message', ''),
                        'last_message_time': msg.get('created_at', datetime.min),
                        'unread_count': 0
                    }
                
                # Update if this message is newer
                msg_time = msg.get('created_at', datetime.min)
                if msg_time > conversations[conv_key]['last_message_time']:
                    conversations[conv_key]['last_message'] = msg.get('message', '')
                    conversations[conv_key]['last_message_time'] = msg_time
                
                # Count unread (messages FROM supplier TO user that are unread)
                is_from_supplier = sender_type == 'supplier' and sender_id == supplier_id
                if is_from_supplier and not msg.get('read', False):
                    conversations[conv_key]['unread_count'] += 1
        
        # Convert to list and sort by most recent
        conversations_list = list(conversations.values())
        conversations_list.sort(key=lambda x: x.get('last_message_time', datetime.min), reverse=True)
        
        print(f"✅ Found {len(conversations_list)} conversations")
        for conv in conversations_list[:5]:
            print(f"   - {conv['sender_name']}: {conv['last_message'][:30]}... (Unread: {conv['unread_count']})")
        print("=" * 80)
        
        return jsonify({'conversations': conversations_list})
        
    except Exception as e:
        print(f"❌ Error loading conversations: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        return jsonify({'conversations': []})


@user_bp.route('/messages/conversation/<recipient_id>')
@login_required
def messages_conversation(recipient_id):
    """Get conversation with a specific contractor or supplier"""
    db = get_db()
    if not db:
        return jsonify({'messages': [], 'contact_info': {}})
    
    recipient_type = request.args.get('type', 'contractor')
    
    try:
        print("=" * 80)
        print(f"📖 LOADING CONVERSATION")
        print(f"User ID: {current_user.id}")
        print(f"Recipient ID: {recipient_id}")
        print(f"Recipient Type: {recipient_type}")
        print("=" * 80)
        
        all_messages = []
        
        if recipient_type == 'contractor':
            # Get ALL messages involving this contractor
            messages_query = db.collection('messages')\
                .where('contractor_id', '==', recipient_id)\
                .stream()
            
            for doc in messages_query:
                msg = doc.to_dict()
                # Only include messages involving this user
                if msg.get('user_id') == current_user.id or msg.get('sender_id') == current_user.id:
                    msg['id'] = doc.id
                    
                    # Determine direction: outgoing if user sent it, incoming otherwise
                    is_user_message = (msg.get('sender_id') == current_user.id and msg.get('sender_type') == 'user')
                    msg['direction'] = 'outgoing' if is_user_message else 'incoming'
                    
                    all_messages.append(msg)
                    print(f"  📨 {msg['direction']}: {msg.get('message')[:40]}...")
            
            # Get contractor info
            contractor_doc = db.collection('contractors').document(recipient_id).get()
            if contractor_doc.exists:
                contractor_data = contractor_doc.to_dict()
                contact_info = {
                    'name': contractor_data.get('company_name') or contractor_data.get('name', 'Contractor'),
                    'email': contractor_data.get('email', ''),
                    'phone': contractor_data.get('phone', '')
                }
            else:
                contact_info = {'name': 'Contractor', 'email': '', 'phone': ''}
        
        else:  # supplier
            # Get ALL messages involving this supplier
            messages_query = db.collection('messages')\
                .where('supplier_id', '==', recipient_id)\
                .stream()
            
            for doc in messages_query:
                msg = doc.to_dict()
                # Only include messages involving this user
                if msg.get('user_id') == current_user.id or msg.get('sender_id') == current_user.id:
                    msg['id'] = doc.id
                    
                    # Determine direction: outgoing if user sent it, incoming otherwise
                    is_user_message = (msg.get('sender_id') == current_user.id and msg.get('sender_type') == 'user')
                    msg['direction'] = 'outgoing' if is_user_message else 'incoming'
                    
                    all_messages.append(msg)
                    print(f"  📨 {msg['direction']}: {msg.get('message')[:40]}...")
            
            # Get supplier info
            supplier_doc = db.collection('suppliers').document(recipient_id).get()
            if supplier_doc.exists:
                supplier_data = supplier_doc.to_dict()
                contact_info = {
                    'name': supplier_data.get('company_name') or supplier_data.get('name', 'Supplier'),
                    'email': supplier_data.get('email', ''),
                    'phone': supplier_data.get('phone', '')
                }
            else:
                contact_info = {'name': 'Supplier', 'email': '', 'phone': ''}
        
        # Sort by created_at (oldest first for chat display)
        all_messages.sort(key=lambda x: x.get('created_at', datetime.min))
        
        # Mark incoming messages as read
        for msg in all_messages:
            if msg['direction'] == 'incoming' and not msg.get('read', False):
                db.collection('messages').document(msg['id']).update({
                    'read': True,
                    'read_at': datetime.now()
                })
        
        print(f"✅ Loaded {len(all_messages)} messages")
        print(f"   Incoming: {len([m for m in all_messages if m['direction'] == 'incoming'])}")
        print(f"   Outgoing: {len([m for m in all_messages if m['direction'] == 'outgoing'])}")
        print("=" * 80)
        
        return jsonify({
            'messages': all_messages,
            'contact_info': contact_info
        })
        
    except Exception as e:
        print(f"❌ Error loading conversation: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        return jsonify({'messages': [], 'contact_info': {}})


@user_bp.route('/messages/send/<recipient_id>', methods=['POST'])
@login_required
def send_message_to_recipient(recipient_id):
    """Send a message to contractor or supplier"""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    recipient_type = request.form.get('recipient_type', 'contractor')
    
    try:
        message_text = request.form.get('message', '').strip()
        
        if not message_text:
            return jsonify({'success': False, 'message': 'Message cannot be empty'}), 400
        
        print("=" * 80)
        print("📤 USER SENDING MESSAGE")
        print(f"User ID: {current_user.id}")
        print(f"Recipient ID: {recipient_id}")
        print(f"Recipient Type: {recipient_type}")
        print(f"Message: {message_text[:50]}...")
        print("=" * 80)
        
        if recipient_type == 'contractor':
            # Get contractor info
            contractor_doc = db.collection('contractors').document(recipient_id).get()
            if not contractor_doc.exists:
                return jsonify({'success': False, 'message': 'Contractor not found'}), 404
            
            contractor_data = contractor_doc.to_dict()
            
            message_data = {
                'user_id': current_user.id,
                'contractor_id': recipient_id,
                'sender_id': current_user.id,
                'sender_type': 'user',
                'sender_name': current_user.name,
                'sender_email': current_user.email if hasattr(current_user, 'email') else '',
                'sender_phone': current_user.phone if hasattr(current_user, 'phone') else '',
                'contractor_name': contractor_data.get('company_name') or contractor_data.get('name'),
                'message': message_text,
                'type': 'chat',
                'read': False,
                'created_at': datetime.now()
            }
        
        else:  # supplier
            # Get supplier info
            supplier_doc = db.collection('suppliers').document(recipient_id).get()
            if not supplier_doc.exists:
                return jsonify({'success': False, 'message': 'Supplier not found'}), 404
            
            supplier_data = supplier_doc.to_dict()
            
            message_data = {
                'user_id': current_user.id,
                'supplier_id': recipient_id,
                'sender_id': current_user.id,
                'sender_type': 'user',
                'sender_name': current_user.name,
                'sender_email': current_user.email if hasattr(current_user, 'email') else '',
                'sender_phone': current_user.phone if hasattr(current_user, 'phone') else '',
                'supplier_name': supplier_data.get('company_name') or supplier_data.get('name'),
                'message': message_text,
                'type': 'chat',
                'read': False,
                'created_at': datetime.now()
            }
        
        doc_ref = db.collection('messages').add(message_data)
        message_id = doc_ref[1].id
        
        print(f"✅ Message sent successfully! ID: {message_id}")
        print("=" * 80)
        
        return jsonify({
            'success': True,
            'message_id': message_id,
            'timestamp': datetime.now().strftime('%I:%M %p')
        })
        
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        return jsonify({'success': False, 'message': str(e)}), 500


@user_bp.route('/messages/unread-count')
@login_required
def messages_unread_count():
    """Get count of unread messages for badge"""
    db = get_db()
    if not db:
        return jsonify({'count': 0})
    
    try:
        # Get all messages for this user
        messages_ref = db.collection('messages').where('user_id', '==', current_user.id).stream()
        
        unread_count = 0
        for doc in messages_ref:
            message_data = doc.to_dict()
            
            # Skip outgoing messages (where user is the sender)
            if message_data.get('sender_id') == current_user.id and message_data.get('sender_type') == 'user':
                continue
            
            # Count unread
            if not message_data.get('read', False):
                unread_count += 1
        
        return jsonify({'count': unread_count})
        
    except Exception as e:
        print(f"Error getting unread count: {e}")
        return jsonify({'count': 0})
    
@user_bp.route('/project/<project_id>/complete', methods=['POST'])
@login_required
def complete_project(project_id):
    """Mark project as completed"""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        project_ref = db.collection('projects').document(project_id)
        project_doc = project_ref.get()
        
        if not project_doc.exists:
            return jsonify({'success': False, 'message': 'Project not found'}), 404
        
        project_data = project_doc.to_dict()
        
        # Verify ownership
        if project_data.get('user_id') != current_user.id:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        
        # Update project status
        project_ref.update({
            'status': 'completed',
            'completed_at': datetime.now(),
            'updated_at': datetime.now()
        })
        
        return jsonify({'success': True, 'message': 'Project marked as completed!'})
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Add to user_routes.py
@user_bp.route('/project/<project_id>/rate-contractor', methods=['POST'])
@login_required
def rate_contractor(project_id):
    """Rate contractor after project completion"""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        project_doc = db.collection('projects').document(project_id).get()
        
        if not project_doc.exists:
            return jsonify({'success': False, 'message': 'Project not found'}), 404
        
        project_data = project_doc.to_dict()
        
        # Verify ownership
        if project_data.get('user_id') != current_user.id:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        
        # Check if project is completed
        if project_data.get('status') != 'completed':
            return jsonify({'success': False, 'message': 'Can only rate completed projects'}), 400
        
        rating = float(request.form.get('rating'))
        review = request.form.get('review', '')
        contractor_id = project_data.get('contractor_id')
        
        if not contractor_id:
            return jsonify({'success': False, 'message': 'No contractor assigned to this project'}), 400
        
        # Save review
        review_data = {
            'project_id': project_id,
            'contractor_id': contractor_id,
            'user_id': current_user.id,
            'user_name': current_user.name,
            'rating': rating,
            'review': review,
            'created_at': datetime.now()
        }
        db.collection('reviews').add(review_data)
        
        # Update contractor's average rating
        reviews = list(db.collection('reviews').where('contractor_id', '==', contractor_id).stream())
        avg_rating = sum(r.to_dict().get('rating', 0) for r in reviews) / len(reviews) if reviews else 0
        
        db.collection('contractors').document(contractor_id).update({
            'rating': round(avg_rating, 1),
            'total_reviews': len(reviews),
            'updated_at': datetime.now()
        })
        
        # Mark project as reviewed
        db.collection('projects').document(project_id).update({
            'reviewed': True,
            'reviewed_at': datetime.now()
        })
        
        # Create notification for contractor
        create_notification(
            contractor_id,
            'New Review Received',
            f'{current_user.name} rated your work {rating}/5 stars',
            'review',
            f'/contractor/reviews'
        )
        
        return jsonify({'success': True, 'message': 'Thank you for your review!'})
        
    except Exception as e:
        print(f"Error rating contractor: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

# Add to user_routes.py
@user_bp.route('/project/<project_id>/updates')
@login_required
def project_updates(project_id):
    """View project progress updates from contractor"""
    db = get_db()
    
    try:
        # Get project
        project_doc = db.collection('projects').document(project_id).get()
        project_data = project_doc.to_dict()
        
        if project_data.get('user_id') != current_user.id:
            flash('Access denied', 'error')
            return redirect(url_for('user.projects'))
        
        # Get all updates
        updates_ref = db.collection('project_updates')\
            .where('project_id', '==', project_id)\
            .order_by('created_at', direction=firestore.Query.DESCENDING)\
            .stream()
        
        updates = []
        for doc in updates_ref:
            update_data = doc.to_dict()
            update_data['id'] = doc.id
            updates.append(update_data)
        
        return render_template('user/project_updates.html', 
                             project=project_data, 
                             updates=updates)
                             
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('user.projects'))
    
@user_bp.route('/project/<project_id>/upload-document', methods=['POST'])
@login_required
def upload_document(project_id):
    """Upload project documents"""
    db = get_db()
    
    try:
        if 'document' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
        
        file = request.files['document']
        doc_type = request.form.get('document_type')  # contract, permit, invoice, etc.
        
        # Save file
        filename = secure_filename(f"{project_id}_{doc_type}_{int(datetime.now().timestamp())}_{file.filename}")
        upload_folder = os.path.join('static', 'uploads', 'documents')
        os.makedirs(upload_folder, exist_ok=True)
        
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        
        # Save document record
        doc_data = {
            'project_id': project_id,
            'user_id': current_user.id,
            'filename': filename,
            'original_name': file.filename,
            'type': doc_type,
            'uploaded_at': datetime.now()
        }
        db.collection('project_documents').add(doc_data)
        
        return jsonify({'success': True, 'filename': filename})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Add to user_routes.py
@user_bp.route('/notifications')
@login_required
def notifications():
    """View all notifications"""
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.dashboard'))
    
    try:
        # Get notifications without order_by to avoid index requirement
        notifications_ref = db.collection('notifications')\
            .where('user_id', '==', current_user.id)\
            .stream()
        
        notifications = []
        unread_count = 0
        
        for doc in notifications_ref:
            notif_data = doc.to_dict()
            notif_data['id'] = doc.id
            notifications.append(notif_data)
            
            if not notif_data.get('read', False):
                unread_count += 1
        
        # Sort in Python instead of Firestore
        notifications.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)
        
        # Limit to 50 most recent
        notifications = notifications[:50]
        
        return render_template('user/notifications.html', 
                             notifications=notifications,
                             unread_count=unread_count)
    except Exception as e:
        print(f"Error loading notifications: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Error loading notifications: {str(e)}', 'error')
        return redirect(url_for('user.dashboard'))

@user_bp.route('/notifications/mark-read/<notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark notification as read"""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        db.collection('notifications').document(notification_id).update({
            'read': True,
            'read_at': datetime.now()
        })
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@user_bp.route('/notifications/unread-count')
@login_required
def notifications_unread_count():
    """Get count of unread notifications"""
    db = get_db()
    if not db:
        return jsonify({'count': 0})
    
    try:
        notifications_ref = db.collection('notifications')\
            .where('user_id', '==', current_user.id)\
            .where('read', '==', False)\
            .stream()
        
        count = len(list(notifications_ref))
        return jsonify({'count': count})
    except Exception as e:
        print(f"Error getting unread count: {e}")
        return jsonify({'count': 0})
    
# ======================== HELPER FUNCTIONS ========================

def create_notification(user_id, title, message, type, link=None):
    """Create a notification for a user"""
    db = firestore.client()
    
    notification_data = {
        'user_id': user_id,
        'title': title,
        'message': message,
        'type': type,  # 'bid', 'message', 'order', 'project', 'payment', 'review'
        'link': link,
        'read': False,
        'created_at': datetime.now()
    }
    
    db.collection('notifications').add(notification_data)

@user_bp.route('/bids')
@login_required
def all_bids():
    """View all bids across all of the user's projects"""
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.dashboard'))

    try:
        # Get all user projects first
        projects_ref = db.collection('projects').where('user_id', '==', current_user.id).stream()
        projects_map = {}
        for doc in projects_ref:
            projects_map[doc.id] = doc.to_dict()
            projects_map[doc.id]['id'] = doc.id

        # Get all bids for those projects
        all_bids = []
        for project_id, project_data in projects_map.items():
            bids_ref = db.collection('bids').where('project_id', '==', project_id).stream()
            for doc in bids_ref:
                bid = doc.to_dict()
                bid['id'] = doc.id
                bid['project_title'] = project_data.get('title', 'Untitled')
                bid['project_id']    = project_id
                all_bids.append(bid)

        # Sort newest first
        all_bids.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)

        stats = {
            'total':    len(all_bids),
            'pending':  len([b for b in all_bids if b.get('status') == 'pending']),
            'accepted': len([b for b in all_bids if b.get('status') == 'accepted']),
            'rejected': len([b for b in all_bids if b.get('status') == 'rejected']),
        }

        # Profile picture for navbar
        user_profile_picture = None
        try:
            user_doc = db.collection('users').document(current_user.id).get()
            if user_doc.exists:
                user_profile_picture = user_doc.to_dict().get('profile_picture')
        except Exception:
            pass

        return render_template('user/all_bids.html',
                               bids=all_bids,
                               stats=stats,
                               user_profile_picture=user_profile_picture)

    except Exception as e:
        flash(f'Error loading bids: {str(e)}', 'error')
        return redirect(url_for('user.dashboard'))

@user_bp.route('/bids/pending-count')
@login_required
def bids_pending_count():
    """Return count of pending bids across all user projects — used by navbar badge"""
    db = get_db()
    if not db:
        return jsonify({'count': 0})
    try:
        projects_ref = db.collection('projects').where('user_id', '==', current_user.id).stream()
        count = 0
        for p_doc in projects_ref:
            bids = db.collection('bids') \
                     .where('project_id', '==', p_doc.id) \
                     .where('status', '==', 'pending') \
                     .stream()
            count += sum(1 for _ in bids)
        return jsonify({'count': count})
    except Exception as e:
        print(f"Error getting pending bid count: {e}")
        return jsonify({'count': 0})