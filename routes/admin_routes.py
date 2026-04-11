from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from functools import wraps

admin_bp = Blueprint('admin', __name__)

def get_db():
    from app import db
    return db

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Admin access required', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


# ── PROJECT CRUD ────────────────────────────────────────────────────────────

@admin_bp.route('/projects')
@login_required
@admin_required
def all_projects():
    db = get_db()

    # ── Pre-fetch all users into a dict — ONE read per user, not per project ──
    user_cache = {}
    try:
        for doc in db.collection('users').stream():
            udata = doc.to_dict()
            user_cache[doc.id] = udata.get('name', '') or udata.get('email', '')
    except Exception as e:
        print(f'[all_projects] could not cache users: {e}')

    projects = []
    for doc in db.collection('projects').stream():
        project_data = doc.to_dict()
        project_data['id'] = doc.id

        # ── Resolve owner name ────────────────────────────────────────────
        if not project_data.get('owner_name') and not project_data.get('user_name'):
            uid = project_data.get('user_id', '')
            project_data['owner_name'] = user_cache.get(uid, '—')

        # ── Derive display budget from embedded estimation ─────────────────
        # Projects store budget_range ('low'/'medium'/'high') + nested estimation.
        # The raw 'budget' field is rarely populated directly, so pull total_cost.
        if not project_data.get('budget'):
            estimation = project_data.get('estimation') or {}
            costs = estimation.get('costs', {})
            budget_tier = project_data.get('budget_range', 'medium')
            tier_data = costs.get(budget_tier) or costs.get('medium') or {}
            total = tier_data.get('total_cost', 0)
            if total:
                project_data['budget'] = total

        projects.append(project_data)

    return render_template('admin/all_projects.html', projects=projects)


@admin_bp.route('/projects/<project_id>')
@login_required
@admin_required
def view_project(project_id):
    """Admin view of a single project — mirrors user project detail."""
    db = get_db()
    doc = db.collection('projects').document(project_id).get()
    if not doc.exists:
        flash('Project not found.', 'error')
        return redirect(url_for('admin.all_projects'))

    project = doc.to_dict()
    project['id'] = doc.id

    # ── Fetch owner name from users collection ────────────────────────────
    user_id = project.get('user_id', '')
    if user_id and not project.get('owner_name') and not project.get('user_name'):
        try:
            user_doc = db.collection('users').document(user_id).get()
            if user_doc.exists:
                udata = user_doc.to_dict()
                project['owner_name'] = udata.get('name', '')
                project['owner_email'] = udata.get('email', '')
                project['owner_phone'] = udata.get('phone', '')
        except Exception as e:
            print(f'[admin view_project] could not fetch owner: {e}')

    # ── Estimation is embedded in the project document (set by user routes) ─
    estimation = project.get('estimation')

    # ── Fallback: try separate estimations collection (legacy) ────────────
    if not estimation:
        try:
            est_doc = db.collection('estimations').document(project_id).get()
            if est_doc.exists:
                estimation = est_doc.to_dict()
        except Exception:
            pass

    # ── Final fallback: safe empty structure so template never crashes ─────
    if not estimation:
        estimation = {
            'costs': {
                'low':    {'material_cost': 0, 'labor_cost': 0, 'other_costs': 0, 'total_cost': 0, 'stage_breakdown': {}},
                'medium': {'material_cost': 0, 'labor_cost': 0, 'other_costs': 0, 'total_cost': 0, 'stage_breakdown': {}},
                'high':   {'material_cost': 0, 'labor_cost': 0, 'other_costs': 0, 'total_cost': 0, 'stage_breakdown': {}},
            },
            'materials': {
                'foundation': {}, 'walls': {}, 'flooring': {}, 'roofing': {},
                'plumbing': {}, 'electrical': {}, 'finishing': {}, 'carpentry': {},
                'exterior': {}, 'miscellaneous': {},
            },
            'timeline': {
                'total_days': 0,
                'foundation': 0, 'walls': 0, 'flooring': 0, 'roofing': 0,
                'plumbing': 0, 'electrical': 0, 'finishing': 0, 'carpentry': 0, 'exterior': 0,
            },
            'ai_success': False,
            'ai_rationale': '',
            'ai_confidence': 0,
            'estimate_scope': project.get('estimate_scope', 'material_only'),
            'property_type': project.get('property_type', 'residential'),
        }

    # ── Ensure nested keys always exist so Jinja never KeyErrors ─────────
    if 'costs' not in estimation:
        estimation['costs'] = {
            'low':    {'material_cost': 0, 'labor_cost': 0, 'other_costs': 0, 'total_cost': 0, 'stage_breakdown': {}},
            'medium': {'material_cost': 0, 'labor_cost': 0, 'other_costs': 0, 'total_cost': 0, 'stage_breakdown': {}},
            'high':   {'material_cost': 0, 'labor_cost': 0, 'other_costs': 0, 'total_cost': 0, 'stage_breakdown': {}},
        }
    for tier in ('low', 'medium', 'high'):
        tier_data = estimation['costs'].setdefault(tier, {})
        tier_data.setdefault('material_cost', 0)
        tier_data.setdefault('labor_cost', 0)
        tier_data.setdefault('other_costs', 0)
        tier_data.setdefault('total_cost', 0)
        tier_data.setdefault('stage_breakdown', {})

    if 'materials' not in estimation or not estimation['materials']:
        estimation['materials'] = {
            'foundation': {}, 'walls': {}, 'flooring': {}, 'roofing': {},
            'plumbing': {}, 'electrical': {}, 'finishing': {}, 'carpentry': {},
            'exterior': {}, 'miscellaneous': {},
        }

    if 'timeline' not in estimation or not estimation['timeline']:
        estimation['timeline'] = {
            'total_days': 0,
            'foundation': 0, 'walls': 0, 'flooring': 0, 'roofing': 0,
            'plumbing': 0, 'electrical': 0, 'finishing': 0, 'carpentry': 0, 'exterior': 0,
        }
    estimation['timeline'].setdefault('total_days', 0)

    return render_template(
        'admin/project_detail.html',
        project=project,
        project_id=project_id,
        estimation=estimation,
    )

@admin_bp.route('/projects/<project_id>/update', methods=['POST'])
@login_required
@admin_required
def update_project(project_id):
    db = get_db()
    data = request.get_json()
    data['updated_at'] = datetime.now()
    data['updated_by'] = current_user.id
    db.collection('projects').document(project_id).update(data)
    return jsonify({'success': True})


@admin_bp.route('/projects/<project_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_project(project_id):
    db = get_db()
    db.collection('projects').document(project_id).delete()
    return jsonify({'success': True})


# ── DASHBOARD ───────────────────────────────────────────────────────────────

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    db = get_db()
    users = list(db.collection('users').stream())
    contractors = list(db.collection('contractors').stream())
    suppliers = list(db.collection('suppliers').stream())
    pending_contractors = [c for c in contractors if not c.to_dict().get('verified', False)]
    pending_suppliers   = [s for s in suppliers   if not s.to_dict().get('verified', False)]
    projects = list(db.collection('projects').stream())
    active_projects = [p for p in projects if p.to_dict().get('status') == 'active']
    orders = list(db.collection('orders').stream())
    total_revenue = sum(
        o.to_dict().get('total', 0)
        for o in orders if o.to_dict().get('status') == 'completed'
    )
    stats = {
        'total_users':         len(users),
        'total_contractors':   len(contractors),
        'total_suppliers':     len(suppliers),
        'pending_verifications': len(pending_contractors) + len(pending_suppliers),
        'total_projects':      len(projects),
        'active_projects':     len(active_projects),
        'total_revenue':       total_revenue,
        'total_platform_users': len(users) + len(contractors) + len(suppliers),
    }
    recent_projects = projects[-5:] if len(projects) > 5 else projects
    return render_template(
        'admin/dashboard.html',
        stats=stats,
        pending_contractors=pending_contractors[:5],
        pending_suppliers=pending_suppliers[:5],
        recent_projects=recent_projects,
    )


# ── USER MANAGEMENT ─────────────────────────────────────────────────────────

@admin_bp.route('/users')
@login_required
@admin_required
def manage_users():
    db = get_db()
    users = []
    for doc in db.collection('users').stream():
        user_data = doc.to_dict()
        user_data['id'] = doc.id
        user_data['type'] = 'user'
        if 'verified' not in user_data:
            user_data['verified'] = False
        if 'active' not in user_data:
            user_data['active'] = True
        users.append(user_data)
    return render_template('admin/manage_users.html', users=users)


@admin_bp.route('/contractors')
@login_required
@admin_required
def manage_contractors():
    db = get_db()
    contractors = []
    for doc in db.collection('contractors').stream():
        contractor_data = doc.to_dict()
        contractor_data['id'] = doc.id
        if 'verified' not in contractor_data:
            contractor_data['verified'] = False
        if 'active' not in contractor_data:
            contractor_data['active'] = True
        contractors.append(contractor_data)
    return render_template('admin/manage_contractors.html', contractors=contractors)


@admin_bp.route('/suppliers')
@login_required
@admin_required
def manage_suppliers():
    db = get_db()
    suppliers = []
    for doc in db.collection('suppliers').stream():
        supplier_data = doc.to_dict()
        supplier_data['id'] = doc.id
        if 'verified' not in supplier_data:
            supplier_data['verified'] = False
        if 'active' not in supplier_data:
            supplier_data['active'] = True
        suppliers.append(supplier_data)
    return render_template('admin/manage_suppliers.html', suppliers=suppliers)


# ── VERIFICATION ─────────────────────────────────────────────────────────────

@admin_bp.route('/verify-contractor/<contractor_id>', methods=['POST'])
@login_required
@admin_required
def verify_contractor(contractor_id):
    db = get_db()
    try:
        db.collection('contractors').document(contractor_id).update({
            'verified': True,
            'verified_at': datetime.now(),
            'verified_by': current_user.id,
        })
        flash('Contractor verified successfully!', 'success')
    except Exception as e:
        flash(f'Error verifying contractor: {str(e)}', 'error')
    return redirect(url_for('admin.manage_contractors'))


@admin_bp.route('/verify-supplier/<supplier_id>', methods=['POST'])
@login_required
@admin_required
def verify_supplier(supplier_id):
    db = get_db()
    try:
        db.collection('suppliers').document(supplier_id).update({
            'verified': True,
            'verified_at': datetime.now(),
            'verified_by': current_user.id,
        })
        flash('Supplier verified successfully!', 'success')
    except Exception as e:
        flash(f'Error verifying supplier: {str(e)}', 'error')
    return redirect(url_for('admin.manage_suppliers'))


@admin_bp.route('/verify-user/<user_id>', methods=['POST'])
@login_required
@admin_required
def verify_user(user_id):
    db = get_db()
    try:
        db.collection('users').document(user_id).update({
            'verified': True,
            'verified_at': datetime.now(),
            'verified_by': current_user.id,
        })
        flash('User verified successfully!', 'success')
    except Exception as e:
        flash(f'Error verifying user: {str(e)}', 'error')
    return redirect(url_for('admin.manage_users'))


# ── ACTIVATE / DEACTIVATE ────────────────────────────────────────────────────

@admin_bp.route('/deactivate-user/<user_type>/<user_id>', methods=['POST'])
@login_required
@admin_required
def deactivate_user(user_type, user_id):
    db = get_db()
    try:
        collection = user_type + 's' if user_type != 'user' else 'users'
        db.collection(collection).document(user_id).update({
            'active': False,
            'deactivated_at': datetime.now(),
            'deactivated_by': current_user.id,
        })
        flash('User deactivated successfully!', 'success')
    except Exception as e:
        flash(f'Error deactivating user: {str(e)}', 'error')
    return redirect(request.referrer or url_for('admin.dashboard'))


@admin_bp.route('/activate-user/<user_type>/<user_id>', methods=['POST'])
@login_required
@admin_required
def activate_user(user_type, user_id):
    db = get_db()
    try:
        collection = user_type + 's' if user_type != 'user' else 'users'
        db.collection(collection).document(user_id).update({
            'active': True,
            'activated_at': datetime.now(),
        })
        flash('User activated successfully!', 'success')
    except Exception as e:
        flash(f'Error activating user: {str(e)}', 'error')
    return redirect(request.referrer or url_for('admin.dashboard'))


@admin_bp.route('/users/<user_id>/profile')
@login_required
@admin_required
def view_user_profile(user_id):
    """Admin view of a specific user's full profile."""
    db = get_db()

    # Fetch user
    user_doc = db.collection('users').document(user_id).get()
    if not user_doc.exists:
        flash('User not found.', 'error')
        return redirect(url_for('admin.manage_users'))

    user_data = user_doc.to_dict()
    user_data['id'] = user_doc.id

    # Fetch their projects
    projects = []
    try:
        for doc in db.collection('projects').where('user_id', '==', user_id).stream():
            pd = doc.to_dict()
            pd['id'] = doc.id
            # Derive budget from estimation
            if not pd.get('budget'):
                est = pd.get('estimation') or {}
                costs = est.get('costs', {})
                tier = pd.get('budget_range', 'medium')
                tier_data = costs.get(tier) or costs.get('medium') or {}
                total = tier_data.get('total_cost', 0)
                if total:
                    pd['budget'] = total
            projects.append(pd)
    except Exception as e:
        print(f'[view_user_profile] could not fetch projects: {e}')

    # Fetch their orders
    orders = []
    try:
        for doc in db.collection('orders').where('user_id', '==', user_id).stream():
            od = doc.to_dict()
            od['id'] = doc.id
            orders.append(od)
    except Exception as e:
        print(f'[view_user_profile] could not fetch orders: {e}')

    orders.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)
    projects.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)

    stats = {
        'total_projects':  len(projects),
        'active_projects': len([p for p in projects if p.get('status') == 'active']),
        'completed_projects': len([p for p in projects if p.get('status') == 'completed']),
        'total_orders':    len(orders),
        'total_spent':     sum(o.get('total', 0) for o in orders if o.get('status') == 'completed'),
    }

    return render_template(
        'admin/user_profile.html',
        user=user_data,
        user_id=user_id,
        projects=projects,
        orders=orders,
        stats=stats,
    )

# ── ORDERS MANAGEMENT ────────────────────────────────────────────────────────

@admin_bp.route('/orders')
@login_required
@admin_required
def all_orders():
    db = get_db()

    # Pre-fetch users and suppliers into caches
    user_cache = {}
    try:
        for doc in db.collection('users').stream():
            udata = doc.to_dict()
            user_cache[doc.id] = {'name': udata.get('name', ''), 'email': udata.get('email', '')}
    except Exception as e:
        print(f'[all_orders] could not cache users: {e}')

    supplier_cache = {}
    try:
        for doc in db.collection('suppliers').stream():
            sdata = doc.to_dict()
            supplier_cache[doc.id] = {'name': sdata.get('company_name') or sdata.get('name', ''), 'email': sdata.get('email', '')}
    except Exception as e:
        print(f'[all_orders] could not cache suppliers: {e}')

    orders = []
    for doc in db.collection('orders').stream():
        order_data = doc.to_dict()
        order_data['id'] = doc.id

        # Resolve user name
        if not order_data.get('user_name'):
            uid = order_data.get('user_id', '')
            ucache = user_cache.get(uid, {})
            order_data['user_name'] = ucache.get('name', '—')
            order_data['user_email'] = ucache.get('email', '')

        # Resolve supplier name
        if not order_data.get('supplier_name'):
            sid = order_data.get('supplier_id', '')
            scache = supplier_cache.get(sid, {})
            order_data['supplier_name'] = scache.get('name', '—')

        orders.append(order_data)

    # Sort newest first
    orders.sort(key=lambda x: x.get('created_at') or datetime.min, reverse=True)

    # Stats
    stats = {
        'total':      len(orders),
        'pending':    sum(1 for o in orders if o.get('status') == 'pending'),
        'processing': sum(1 for o in orders if o.get('status') == 'processing'),
        'completed':  sum(1 for o in orders if o.get('status') == 'completed'),
        'cancelled':  sum(1 for o in orders if o.get('status') == 'cancelled'),
        'total_revenue': sum(
            o.get('total', 0) for o in orders if o.get('status') == 'completed'
        ),
    }

    return render_template('admin/all_orders.html', orders=orders, stats=stats)


@admin_bp.route('/orders/<order_id>')
@login_required
@admin_required
def view_order(order_id):
    """Admin detail view for a single order."""
    db = get_db()
    doc = db.collection('orders').document(order_id).get()
    if not doc.exists:
        flash('Order not found.', 'error')
        return redirect(url_for('admin.all_orders'))

    order = doc.to_dict()
    order['id'] = doc.id

    # Fetch user details
    user = {}
    if order.get('user_id'):
        try:
            u = db.collection('users').document(order['user_id']).get()
            if u.exists:
                user = u.to_dict()
                user['id'] = u.id
        except Exception as e:
            print(f'[admin view_order] user fetch error: {e}')

    # Fetch supplier details
    supplier = {}
    if order.get('supplier_id'):
        try:
            s = db.collection('suppliers').document(order['supplier_id']).get()
            if s.exists:
                supplier = s.to_dict()
                supplier['id'] = s.id
        except Exception as e:
            print(f'[admin view_order] supplier fetch error: {e}')

    # Fetch linked project
    project = {}
    if order.get('project_id'):
        try:
            p = db.collection('projects').document(order['project_id']).get()
            if p.exists:
                project = p.to_dict()
                project['id'] = p.id
        except Exception as e:
            print(f'[admin view_order] project fetch error: {e}')

    return render_template(
        'admin/order_detail.html',
        order=order,
        order_id=order_id,
        user=user,
        supplier=supplier,
        project=project,
    )


@admin_bp.route('/orders/<order_id>/update', methods=['POST'])
@login_required
@admin_required
def update_order(order_id):
    db = get_db()
    data = request.get_json()
    data['updated_at'] = datetime.now()
    data['updated_by'] = current_user.id
    db.collection('orders').document(order_id).update(data)
    return jsonify({'success': True})


@admin_bp.route('/orders/<order_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_order(order_id):
    db = get_db()
    db.collection('orders').document(order_id).delete()
    return jsonify({'success': True})