from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from firebase_admin import firestore
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import json

supplier_bp = Blueprint('supplier', __name__)
db = firestore.client()

@supplier_bp.route('/dashboard')
@login_required
def dashboard():
    """Supplier Dashboard - Main page after login"""
    
    # Get supplier's materials
    materials_ref = db.collection('materials').where('supplier_id', '==', current_user.id).stream()
    materials = []
    for doc in materials_ref:
        material_data = doc.to_dict()
        material_data['id'] = doc.id
        materials.append(material_data)
    
    # Get orders
    orders_ref = db.collection('orders').where('supplier_id', '==', current_user.id).stream()
    orders = []
    total_revenue = 0
    pending_orders = 0
    
    for doc in orders_ref:
        order_data = doc.to_dict()
        order_data['id'] = doc.id
        orders.append(order_data)
        
        if order_data.get('status') == 'completed':
            total_revenue += order_data.get('total', 0)
        if order_data.get('status') == 'pending':
            pending_orders += 1
    
    stats = {
        'total_materials': len(materials),
        'total_orders': len(orders),
        'pending_orders': pending_orders,
        'total_revenue': total_revenue,
        'rating': current_user.rating if hasattr(current_user, 'rating') else 0.0,
        'verified': current_user.verified if hasattr(current_user, 'verified') else False
    }
    
    return render_template('supplier/dashboard.html',
                         stats=stats,
                         orders=orders[:5])  # Show only 5 recent orders

@supplier_bp.route('/inventory')
@login_required
def inventory():
    """View and manage inventory"""
    materials_ref = db.collection('materials').where('supplier_id', '==', current_user.id).stream()
    materials = []
    for doc in materials_ref:
        material_data = doc.to_dict()
        material_data['id'] = doc.id
        materials.append(material_data)
    
    return render_template('supplier/inventory.html', materials=materials)

@supplier_bp.route('/orders')
@login_required
def orders():
    """View all orders"""
    orders_ref = db.collection('orders').where('supplier_id', '==', current_user.id).stream()
    orders = []
    for doc in orders_ref:
        order_data = doc.to_dict()
        order_data['id'] = doc.id
        orders.append(order_data)
    
    return render_template('supplier/orders.html', orders=orders)

@supplier_bp.route('/add-material', methods=['GET', 'POST'])
@login_required
def add_material():
    """Add new material to inventory"""
    if request.method == 'POST':
        material_data = {
            'supplier_id': current_user.id,
            'supplier_name': current_user.company_name or current_user.name,
            'name': request.form.get('name'),
            'category': request.form.get('category'),
            'price': float(request.form.get('price')),
            'unit': request.form.get('unit'),
            'quantity': int(request.form.get('quantity')),
            'description': request.form.get('description'),
            'created_at': datetime.now()
        }
        
        db.collection('materials').add(material_data)
        flash('Material added successfully!', 'success')
        return redirect(url_for('supplier.inventory'))
    
    return render_template('supplier/add_material.html')

@supplier_bp.route('/profile')
@login_required
def profile():
    """Supplier Profile Page"""
    try:
        print("=" * 50)
        print("SUPPLIER PROFILE ROUTE HIT")
        print(f"Current User ID: {current_user.id}")
        print("=" * 50)
        
        # Get supplier data from 'suppliers' collection
        supplier_ref = db.collection('suppliers').document(current_user.id)
        supplier_doc = supplier_ref.get()
        
        if not supplier_doc.exists:
            print("⚠️ Supplier document not found - Creating default profile...")
            # Create from current_user data
            supplier_data = {
                'name': getattr(current_user, 'name', ''),
                'email': getattr(current_user, 'email', ''),
                'role': 'supplier',
                'company_name': getattr(current_user, 'company_name', ''),
                'phone': getattr(current_user, 'phone', ''),
                'location': getattr(current_user, 'location', ''),
                'bio': getattr(current_user, 'bio', ''),
                'business_license': getattr(current_user, 'business_license', ''),
                'business_type': getattr(current_user, 'business_type', 'wholesaler'),
                'gst_number': getattr(current_user, 'gst_number', ''),
                'years_in_business': getattr(current_user, 'years_in_business', 0),
                'categories': getattr(current_user, 'categories', []),
                'verified': getattr(current_user, 'verified', False),
                'rating': getattr(current_user, 'rating', 0.0),
                'total_orders': getattr(current_user, 'total_orders', 0),
                'profile_picture': getattr(current_user, 'profile_picture', ''),
                'created_at': datetime.now()
            }
            supplier_ref.set(supplier_data)
            print("✅ Default profile created")
        else:
            supplier_data = supplier_doc.to_dict()
            print(f"✅ Supplier data loaded: {supplier_data.get('name')}")
        
        # Convert datetime to string if needed
        if 'created_at' in supplier_data and supplier_data['created_at']:
            try:
                supplier_data['created_at'] = supplier_data['created_at'].strftime('%Y-%m-%d')
            except:
                supplier_data['created_at'] = 'N/A'
        else:
            supplier_data['created_at'] = 'N/A'
        
        # Map field names if different
        if 'active' in supplier_data:
            supplier_data['verified'] = supplier_data['active']
        
        # Count materials
        materials_count = 0
        try:
            materials = list(db.collection('materials').where('supplier_id', '==', current_user.id).stream())
            materials_count = len(materials)
        except Exception as e:
            print(f"Error counting materials: {e}")
        
        # Set defaults
        defaults = {
            'name': '',
            'email': '',
            'company_name': '',
            'business_type': 'wholesaler',
            'phone': '',
            'location': '',
            'bio': '',
            'business_license': '',
            'gst_number': '',
            'years_in_business': 0,
            'categories': [],
            'verified': False,
            'rating': 0.0,
            'total_orders': 0,
            'profile_picture': ''
        }
        
        for key, value in defaults.items():
            if key not in supplier_data:
                supplier_data[key] = value
        
        return render_template('supplier/profile.html',
                             supplier_data=supplier_data,
                             materials_count=materials_count)
    
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        flash('An error occurred while loading your profile', 'error')
        return redirect(url_for('supplier.dashboard'))

@supplier_bp.route('/update_business_info', methods=['POST'])
@login_required
def update_business_info():
    """Update supplier business and personal information"""
    try:
        # Business Information
        company_name = request.form.get('company_name')
        business_type = request.form.get('business_type', 'wholesaler')
        business_license = request.form.get('business_license', '')
        gst_number = request.form.get('gst_number', '')
        years_in_business = int(request.form.get('years_in_business', 0))
        phone = request.form.get('phone')
        location = request.form.get('location')
        bio = request.form.get('bio', '')
        
        # Personal Information
        name = request.form.get('name')
        email = request.form.get('email')
        
        supplier_ref = db.collection('suppliers').document(current_user.id)
        supplier_ref.update({
            # Business Info
            'company_name': company_name,
            'business_type': business_type,
            'business_license': business_license,
            'gst_number': gst_number,
            'years_in_business': years_in_business,
            'phone': phone,
            'location': location,
            'bio': bio,
            # Personal Info
            'name': name,
            'email': email,
            'updated_at': datetime.now()
        })
        
        return jsonify({'success': True, 'message': 'Profile updated successfully'})
    
    except Exception as e:
        print(f"Error updating profile: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@supplier_bp.route('/update_personal_info', methods=['POST'])
@login_required
def update_personal_info():
    """Update supplier personal information"""
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        
        supplier_ref = db.collection('suppliers').document(current_user.id)
        supplier_ref.update({
            'name': name,
            'email': email,
            'updated_at': datetime.now()
        })
        
        return jsonify({'success': True, 'message': 'Personal information updated successfully'})
    
    except Exception as e:
        print(f"Error updating personal info: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@supplier_bp.route('/upload_profile_picture', methods=['POST'])
@login_required
def upload_profile_picture():
    """Upload supplier profile picture"""
    try:
        if 'profile_picture' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
        
        file = request.files['profile_picture']
        
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        
        if file_ext not in allowed_extensions:
            return jsonify({'success': False, 'message': 'Invalid file type'}), 400
        
        filename = secure_filename(f"supplier_{current_user.id}_{int(datetime.now().timestamp())}.{file_ext}")
        
        upload_folder = os.path.join('static', 'uploads', 'profiles')
        os.makedirs(upload_folder, exist_ok=True)
        
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        
        supplier_ref = db.collection('suppliers').document(current_user.id)
        supplier_ref.update({
            'profile_picture': filename,
            'updated_at': datetime.now()
        })
        
        return jsonify({'success': True, 'message': 'Profile picture uploaded successfully', 'filename': filename})
    
    except Exception as e:
        print(f"Error uploading profile picture: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@supplier_bp.route('/upload_documents', methods=['POST'])
@login_required
def upload_documents():
    """Upload supplier business documents"""
    try:
        uploaded_files = []
        
        # Process all uploaded files
        for key in request.files:
            file = request.files[key]
            
            if file.filename == '':
                continue
            
            allowed_extensions = {'pdf', 'doc', 'docx'}
            file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
            
            if file_ext not in allowed_extensions:
                return jsonify({'success': False, 'message': f'Invalid file type: {file.filename}'}), 400
            
            filename = secure_filename(f"supplier_{current_user.id}_doc_{int(datetime.now().timestamp())}_{file.filename}")
            
            upload_folder = os.path.join('static', 'uploads', 'documents')
            os.makedirs(upload_folder, exist_ok=True)
            
            filepath = os.path.join(upload_folder, filename)
            file.save(filepath)
            
            uploaded_files.append({
                'original_name': file.filename,
                'stored_name': filename,
                'uploaded_at': datetime.now()
            })
        
        if not uploaded_files:
            return jsonify({'success': False, 'message': 'No files uploaded'}), 400
        
        # Store document references in supplier profile
        supplier_ref = db.collection('suppliers').document(current_user.id)
        supplier_doc = supplier_ref.get()
        supplier_data = supplier_doc.to_dict() if supplier_doc.exists else {}
        
        existing_docs = supplier_data.get('documents', [])
        existing_docs.extend(uploaded_files)
        
        supplier_ref.update({
            'documents': existing_docs,
            'updated_at': datetime.now()
        })
        
        return jsonify({
            'success': True, 
            'message': f'{len(uploaded_files)} document(s) uploaded successfully',
            'files': uploaded_files
        })
    
    except Exception as e:
        print(f"Error uploading documents: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@supplier_bp.route('/change_password', methods=['POST'])
@login_required
def change_password():
    """Change supplier password"""
    try:
        current_password = request.form.get('currentPassword')
        new_password = request.form.get('newPassword')
        
        supplier_ref = db.collection('suppliers').document(current_user.id)
        supplier_doc = supplier_ref.get()
        
        if not supplier_doc.exists:
            return jsonify({'success': False, 'message': 'Supplier not found'}), 404
        
        supplier_data = supplier_doc.to_dict()
        
        if not check_password_hash(supplier_data.get('password', ''), current_password):
            return jsonify({'success': False, 'message': 'Current password is incorrect'}), 400
        
        hashed_password = generate_password_hash(new_password)
        supplier_ref.update({
            'password': hashed_password,
            'updated_at': datetime.now()
        })
        
        return jsonify({'success': True, 'message': 'Password changed successfully'})
    
    except Exception as e:
        print(f"Error changing password: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500