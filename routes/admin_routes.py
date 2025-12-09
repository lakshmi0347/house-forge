from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from firebase_admin import firestore
from datetime import datetime
from functools import wraps

admin_bp = Blueprint('admin', __name__)
db = firestore.client()

# Admin-only decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Admin access required', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin Dashboard - Overview of entire platform"""
    
    # Get all users count
    users = list(db.collection('users').stream())
    contractors = list(db.collection('contractors').stream())
    suppliers = list(db.collection('suppliers').stream())
    
    # Get pending verifications
    pending_contractors = [c for c in contractors if not c.to_dict().get('verified', False)]
    pending_suppliers = [s for s in suppliers if not s.to_dict().get('verified', False)]
    
    # Get all projects
    projects = list(db.collection('projects').stream())
    active_projects = [p for p in projects if p.to_dict().get('status') == 'active']
    
    # Get total revenue (from completed orders)
    orders = list(db.collection('orders').stream())
    total_revenue = sum(o.to_dict().get('total', 0) for o in orders if o.to_dict().get('status') == 'completed')
    
    stats = {
        'total_users': len(users),
        'total_contractors': len(contractors),
        'total_suppliers': len(suppliers),
        'pending_verifications': len(pending_contractors) + len(pending_suppliers),
        'total_projects': len(projects),
        'active_projects': len(active_projects),
        'total_revenue': total_revenue,
        'total_platform_users': len(users) + len(contractors) + len(suppliers)
    }
    
    # Recent activity
    recent_users = users[-5:] if len(users) > 5 else users
    recent_projects = projects[-5:] if len(projects) > 5 else projects
    
    return render_template('admin/dashboard.html',
                         stats=stats,
                         pending_contractors=pending_contractors[:5],
                         pending_suppliers=pending_suppliers[:5],
                         recent_projects=recent_projects)

@admin_bp.route('/users')
@login_required
@admin_required
def manage_users():
    """View and manage all users"""
    users = []
    for doc in db.collection('users').stream():
        user_data = doc.to_dict()
        user_data['id'] = doc.id
        user_data['type'] = 'user'
        users.append(user_data)
    
    return render_template('admin/manage_users.html', users=users)

@admin_bp.route('/contractors')
@login_required
@admin_required
def manage_contractors():
    """View and manage all contractors"""
    contractors = []
    for doc in db.collection('contractors').stream():
        contractor_data = doc.to_dict()
        contractor_data['id'] = doc.id
        contractors.append(contractor_data)
    
    return render_template('admin/manage_contractors.html', contractors=contractors)

@admin_bp.route('/suppliers')
@login_required
@admin_required
def manage_suppliers():
    """View and manage all suppliers"""
    suppliers = []
    for doc in db.collection('suppliers').stream():
        supplier_data = doc.to_dict()
        supplier_data['id'] = doc.id
        suppliers.append(supplier_data)
    
    return render_template('admin/manage_suppliers.html', suppliers=suppliers)

@admin_bp.route('/verify-contractor/<contractor_id>', methods=['POST'])
@login_required
@admin_required
def verify_contractor(contractor_id):
    """Verify a contractor"""
    try:
        db.collection('contractors').document(contractor_id).update({
            'verified': True,
            'verified_at': datetime.now(),
            'verified_by': current_user.id
        })
        flash('Contractor verified successfully!', 'success')
    except Exception as e:
        flash(f'Error verifying contractor: {str(e)}', 'error')
    
    return redirect(url_for('admin.manage_contractors'))

@admin_bp.route('/verify-supplier/<supplier_id>', methods=['POST'])
@login_required
@admin_required
def verify_supplier(supplier_id):
    """Verify a supplier"""
    try:
        db.collection('suppliers').document(supplier_id).update({
            'verified': True,
            'verified_at': datetime.now(),
            'verified_by': current_user.id
        })
        flash('Supplier verified successfully!', 'success')
    except Exception as e:
        flash(f'Error verifying supplier: {str(e)}', 'error')
    
    return redirect(url_for('admin.manage_suppliers'))

@admin_bp.route('/deactivate-user/<user_type>/<user_id>', methods=['POST'])
@login_required
@admin_required
def deactivate_user(user_type, user_id):
    """Deactivate/Block a user"""
    try:
        collection = user_type + 's' if user_type != 'user' else 'users'
        db.collection(collection).document(user_id).update({
            'active': False,
            'deactivated_at': datetime.now(),
            'deactivated_by': current_user.id
        })
        flash('User deactivated successfully!', 'success')
    except Exception as e:
        flash(f'Error deactivating user: {str(e)}', 'error')
    
    return redirect(request.referrer or url_for('admin.dashboard'))

@admin_bp.route('/activate-user/<user_type>/<user_id>', methods=['POST'])
@login_required
@admin_required
def activate_user(user_type, user_id):
    """Activate/Unblock a user"""
    try:
        collection = user_type + 's' if user_type != 'user' else 'users'
        db.collection(collection).document(user_id).update({
            'active': True,
            'activated_at': datetime.now()
        })
        flash('User activated successfully!', 'success')
    except Exception as e:
        flash(f'Error activating user: {str(e)}', 'error')
    
    return redirect(request.referrer or url_for('admin.dashboard'))

@admin_bp.route('/projects')
@login_required
@admin_required
def all_projects():
    """View all projects"""
    projects = []
    for doc in db.collection('projects').stream():
        project_data = doc.to_dict()
        project_data['id'] = doc.id
        projects.append(project_data)
    
    return render_template('admin/all_projects.html', projects=projects)

@admin_bp.route('/analytics')
@login_required
@admin_required
def analytics():
    """Platform analytics and reports"""
    # Collect analytics data
    users = list(db.collection('users').stream())
    contractors = list(db.collection('contractors').stream())
    suppliers = list(db.collection('suppliers').stream())
    projects = list(db.collection('projects').stream())
    orders = list(db.collection('orders').stream())
    
    analytics_data = {
        'user_growth': len(users),
        'contractor_growth': len(contractors),
        'supplier_growth': len(suppliers),
        'project_completion_rate': 0,  # Calculate based on your logic
        'total_revenue': sum(o.to_dict().get('total', 0) for o in orders if o.to_dict().get('status') == 'completed'),
        'active_users': len([u for u in users if u.to_dict().get('active', True)])
    }
    
    return render_template('admin/analytics.html', analytics=analytics_data)