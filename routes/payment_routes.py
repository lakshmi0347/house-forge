from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from firebase_admin import firestore
from datetime import datetime
import uuid

payment_bp = Blueprint('payment', __name__)
db = firestore.client()


def get_db():
    try:
        return firestore.client()
    except Exception as e:
        print(f"Error getting database: {e}")
        return None


def _get_profile_picture(db):
    try:
        doc = db.collection('users').document(current_user.id).get()
        if doc.exists:
            return doc.to_dict().get('profile_picture')
    except Exception:
        pass
    return None


def _generate_receipt_number():
    """Generate a unique human-readable receipt number."""
    ts  = datetime.now().strftime('%Y%m%d%H%M%S')
    uid = str(uuid.uuid4()).replace('-', '').upper()[:6]
    return f"HF-{ts}-{uid}"


def _create_notification(user_id, title, message, notif_type, link=None):
    try:
        db.collection('notifications').add({
            'user_id':    user_id,
            'title':      title,
            'message':    message,
            'type':       notif_type,
            'link':       link,
            'read':       False,
            'created_at': datetime.now()
        })
    except Exception as e:
        print(f"Notification error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  MATERIAL ORDER PAYMENT  (COD)
# ─────────────────────────────────────────────────────────────────────────────

@payment_bp.route('/order/<order_id>/pay', methods=['GET'])
@login_required
def pay_order(order_id):
    """Show COD confirmation page for a material order."""
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.my_orders'))

    try:
        order_doc = db.collection('orders').document(order_id).get()
        if not order_doc.exists:
            flash('Order not found', 'error')
            return redirect(url_for('user.my_orders'))

        order_data        = order_doc.to_dict()
        order_data['id']  = order_id

        # Only the order owner can pay
        if order_data.get('user_id') != current_user.id:
            flash('Access denied', 'error')
            return redirect(url_for('user.my_orders'))

        # Only processing orders can be paid (supplier has accepted)
        if order_data.get('status') not in ('processing', 'pending'):
            flash('This order is not eligible for payment', 'error')
            return redirect(url_for('user.my_orders'))

        # Already paid?
        if order_data.get('payment_status') == 'paid':
            return redirect(url_for('payment.order_receipt', order_id=order_id))

        if 'items' in order_data:
            order_data['order_items'] = order_data['items']

        user_profile_picture = _get_profile_picture(db)

        return render_template(
            'payment/pay_order.html',
            order=order_data,
            user_profile_picture=user_profile_picture
        )

    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('user.my_orders'))


@payment_bp.route('/order/<order_id>/confirm-cod', methods=['POST'])
@login_required
def confirm_order_cod(order_id):
    """Confirm COD for a material order."""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500

    try:
        order_ref = db.collection('orders').document(order_id)
        order_doc = order_ref.get()

        if not order_doc.exists:
            return jsonify({'success': False, 'message': 'Order not found'}), 404

        order_data = order_doc.to_dict()

        if order_data.get('user_id') != current_user.id:
            return jsonify({'success': False, 'message': 'Access denied'}), 403

        if order_data.get('payment_status') == 'paid':
            return jsonify({'success': False, 'message': 'Order already paid'}), 400

        receipt_number = _generate_receipt_number()

        # Update order
        order_ref.update({
            'payment_status': 'cod_confirmed',
            'payment_method': 'cash_on_delivery',
            'receipt_number': receipt_number,
            'payment_confirmed_at': datetime.now(),
            'status': 'processing',         # keep processing until delivery
            'updated_at': datetime.now()
        })

        # Store payment record
        payment_data = {
            'type':           'material_order',
            'order_id':       order_id,
            'user_id':        current_user.id,
            'user_name':      current_user.name,
            'supplier_id':    order_data.get('supplier_id'),
            'supplier_name':  order_data.get('supplier_name'),
            'amount':         order_data.get('total', 0),
            'method':         'cash_on_delivery',
            'status':         'cod_confirmed',
            'receipt_number': receipt_number,
            'project_title':  order_data.get('project_title', ''),
            'created_at':     datetime.now()
        }
        db.collection('payments').add(payment_data)

        # Notify supplier
        supplier_id = order_data.get('supplier_id')
        if supplier_id:
            _create_notification(
                supplier_id,
                'COD Payment Confirmed',
                f'{current_user.name} has confirmed Cash on Delivery for Order #{order_id[:8]}. '
                f'Amount: ₹{order_data.get("total", 0):,.0f}',
                'payment',
                f'/supplier/order/{order_id}'
            )

        return jsonify({
            'success':        True,
            'message':        'COD confirmed successfully!',
            'receipt_number': receipt_number,
            'redirect_url':   url_for('payment.order_receipt', order_id=order_id)
        })

    except Exception as e:
        print(f"COD confirm error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@payment_bp.route('/order/<order_id>/receipt')
@login_required
def order_receipt(order_id):
    """Show payment receipt for a material order."""
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.my_orders'))

    try:
        order_doc = db.collection('orders').document(order_id).get()
        if not order_doc.exists:
            flash('Order not found', 'error')
            return redirect(url_for('user.my_orders'))

        order_data       = order_doc.to_dict()
        order_data['id'] = order_id

        if order_data.get('user_id') != current_user.id:
            flash('Access denied', 'error')
            return redirect(url_for('user.my_orders'))

        if 'items' in order_data:
            order_data['order_items'] = order_data['items']

        user_profile_picture = _get_profile_picture(db)

        return render_template(
            'payment/order_receipt.html',
            order=order_data,
            user_profile_picture=user_profile_picture
        )

    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('user.my_orders'))


# ─────────────────────────────────────────────────────────────────────────────
#  CONTRACTOR PAYMENT  (COD)
# ─────────────────────────────────────────────────────────────────────────────

@payment_bp.route('/project/<project_id>/pay-contractor', methods=['GET'])
@login_required
def pay_contractor(project_id):
    """Show COD confirmation page for contractor payment."""
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.projects'))

    try:
        project_doc = db.collection('projects').document(project_id).get()
        if not project_doc.exists:
            flash('Project not found', 'error')
            return redirect(url_for('user.projects'))

        project_data       = project_doc.to_dict()
        project_data['id'] = project_id

        if project_data.get('user_id') != current_user.id:
            flash('Access denied', 'error')
            return redirect(url_for('user.projects'))

        if not project_data.get('contractor_id'):
            flash('No contractor assigned to this project yet', 'error')
            return redirect(url_for('user.view_project', project_id=project_id))

        if project_data.get('contractor_payment_status') == 'paid':
            return redirect(url_for('payment.contractor_receipt', project_id=project_id))

        # Fetch contractor info
        contractor_doc  = db.collection('contractors').document(project_data['contractor_id']).get()
        contractor_data = contractor_doc.to_dict() if contractor_doc.exists else {}

        user_profile_picture = _get_profile_picture(db)

        return render_template(
            'payment/pay_contractor.html',
            project=project_data,
            contractor=contractor_data,
            user_profile_picture=user_profile_picture
        )

    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('user.projects'))


@payment_bp.route('/project/<project_id>/confirm-contractor-cod', methods=['POST'])
@login_required
def confirm_contractor_cod(project_id):
    """Confirm COD for contractor payment."""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500

    try:
        project_ref = db.collection('projects').document(project_id)
        project_doc = project_ref.get()

        if not project_doc.exists:
            return jsonify({'success': False, 'message': 'Project not found'}), 404

        project_data = project_doc.to_dict()

        if project_data.get('user_id') != current_user.id:
            return jsonify({'success': False, 'message': 'Access denied'}), 403

        if project_data.get('contractor_payment_status') == 'paid':
            return jsonify({'success': False, 'message': 'Contractor already paid'}), 400

        if not project_data.get('contractor_id'):
            return jsonify({'success': False, 'message': 'No contractor assigned'}), 400

        receipt_number = _generate_receipt_number()
        amount         = project_data.get('agreed_cost', 0)
        contractor_id  = project_data.get('contractor_id')

        # Update project
        project_ref.update({
            'contractor_payment_status':   'cod_confirmed',
            'contractor_payment_method':   'cash_on_delivery',
            'contractor_receipt_number':   receipt_number,
            'contractor_payment_confirmed_at': datetime.now(),
            'updated_at': datetime.now()
        })

        # Store payment record
        payment_data = {
            'type':            'contractor_payment',
            'project_id':      project_id,
            'project_title':   project_data.get('title', ''),
            'user_id':         current_user.id,
            'user_name':       current_user.name,
            'contractor_id':   contractor_id,
            'contractor_name': project_data.get('contractor_name', ''),
            'amount':          amount,
            'method':          'cash_on_delivery',
            'status':          'cod_confirmed',
            'receipt_number':  receipt_number,
            'created_at':      datetime.now()
        }
        db.collection('payments').add(payment_data)

        # Notify contractor
        _create_notification(
            contractor_id,
            'Payment Confirmed (COD)',
            f'{current_user.name} has confirmed Cash on Delivery payment of '
            f'₹{amount:,.0f} for project "{project_data.get("title", "")}".',
            'payment',
            f'/contractor/projects'
        )

        return jsonify({
            'success':        True,
            'message':        'Contractor payment confirmed!',
            'receipt_number': receipt_number,
            'redirect_url':   url_for('payment.contractor_receipt', project_id=project_id)
        })

    except Exception as e:
        print(f"Contractor COD confirm error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@payment_bp.route('/project/<project_id>/contractor-receipt')
@login_required
def contractor_receipt(project_id):
    """Show payment receipt for contractor payment."""
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.projects'))

    try:
        project_doc = db.collection('projects').document(project_id).get()
        if not project_doc.exists:
            flash('Project not found', 'error')
            return redirect(url_for('user.projects'))

        project_data       = project_doc.to_dict()
        project_data['id'] = project_id

        if project_data.get('user_id') != current_user.id:
            flash('Access denied', 'error')
            return redirect(url_for('user.projects'))

        contractor_doc  = db.collection('contractors').document(project_data.get('contractor_id', '')).get()
        contractor_data = contractor_doc.to_dict() if contractor_doc.exists else {}

        user_profile_picture = _get_profile_picture(db)

        return render_template(
            'payment/contractor_receipt.html',
            project=project_data,
            contractor=contractor_data,
            user_profile_picture=user_profile_picture
        )

    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('user.projects'))


# ─────────────────────────────────────────────────────────────────────────────
#  PAYMENT HISTORY
# ─────────────────────────────────────────────────────────────────────────────

@payment_bp.route('/history')
@login_required
def payment_history():
    """Show all payments made by the user."""
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('user.dashboard'))

    try:
        payments_ref = db.collection('payments') \
            .where('user_id', '==', current_user.id) \
            .stream()

        payments = []
        for doc in payments_ref:
            p       = doc.to_dict()
            p['id'] = doc.id
            payments.append(p)

        payments.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)

        total_spent = sum(p.get('amount', 0) for p in payments)

        user_profile_picture = _get_profile_picture(db)

        return render_template(
            'payment/history.html',
            payments=payments,
            total_spent=total_spent,
            user_profile_picture=user_profile_picture
        )

    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('user.dashboard'))


# ─────────────────────────────────────────────────────────────────────────────
#  SUPPLIER: mark order as cash collected (delivery done)
# ─────────────────────────────────────────────────────────────────────────────

@payment_bp.route('/supplier/order/<order_id>/collect-cash', methods=['POST'])
@login_required
def supplier_collect_cash(order_id):
    """Supplier marks cash as collected on delivery."""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500

    try:
        order_ref = db.collection('orders').document(order_id)
        order_doc = order_ref.get()

        if not order_doc.exists:
            return jsonify({'success': False, 'message': 'Order not found'}), 404

        order_data = order_doc.to_dict()

        if order_data.get('supplier_id') != current_user.id:
            return jsonify({'success': False, 'message': 'Access denied'}), 403

        if order_data.get('payment_status') == 'paid':
            return jsonify({'success': False, 'message': 'Already marked as paid'}), 400

        order_ref.update({
            'payment_status':    'paid',
            'cash_collected_at': datetime.now(),
            'status':            'completed',
            'updated_at':        datetime.now()
        })

        # Update payment record status
        payments_ref = db.collection('payments') \
            .where('order_id', '==', order_id) \
            .stream()
        for pdoc in payments_ref:
            db.collection('payments').document(pdoc.id).update({'status': 'paid'})

        # Notify user
        user_id = order_data.get('user_id')
        if user_id:
            _create_notification(
                user_id,
                'Cash Collected — Order Complete',
                f'Your order #{order_id[:8]} has been delivered and payment collected. '
                f'Amount: ₹{order_data.get("total", 0):,.0f}',
                'payment',
                f'/user/my-orders'
            )

        return jsonify({'success': True, 'message': 'Cash collected and order marked as completed!'})

    except Exception as e:
        print(f"Collect cash error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500