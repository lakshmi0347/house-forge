from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from firebase_admin import firestore
from datetime import datetime
import uuid

payment_bp = Blueprint('payment', __name__)


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
    db = get_db()
    if not db:
        return
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


def _deduct_stock(db, order_items):
    """
    Reduce material stock for each item in a delivered order.
    Silently logs errors — stock deduction is non-fatal.
    """
    if not order_items:
        return
    for item in order_items:
        material_id = item.get('material_id')
        qty         = int(item.get('quantity', 0))
        if not material_id or qty <= 0:
            continue
        try:
            mat_ref = db.collection('materials').document(material_id)
            mat_doc = mat_ref.get()
            if mat_doc.exists:
                current_qty = int(mat_doc.to_dict().get('quantity', 0))
                new_qty     = max(0, current_qty - qty)
                mat_ref.update({
                    'quantity':   new_qty,
                    'updated_at': datetime.now()
                })
                print(f"✅ Stock updated: material={material_id} {current_qty} → {new_qty}")
        except Exception as e:
            print(f"⚠️  Stock deduction error for material {material_id}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  INSTANT CHECKOUT PAGE
# ─────────────────────────────────────────────────────────────────────────────

@payment_bp.route('/checkout/<order_id>', methods=['GET'])
@login_required
def checkout(order_id):
    """
    Instant checkout page shown right after the user places a material order.
    """
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

        # If already paid redirect straight to receipt
        if order_data.get('payment_status') in ('paid', 'cod_confirmed', 'card_pending'):
            return redirect(url_for('payment.order_receipt', order_id=order_id))

        # Normalise items key
        if 'items' in order_data:
            order_data['order_items'] = order_data['items']

        user_profile_picture = _get_profile_picture(db)

        return render_template(
            'payment/checkout.html',
            order=order_data,
            user_profile_picture=user_profile_picture
        )

    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('user.my_orders'))


# ─────────────────────────────────────────────────────────────────────────────
#  MATERIAL ORDER PAYMENT  (legacy pay_order kept for backwards compatibility)
# ─────────────────────────────────────────────────────────────────────────────

@payment_bp.route('/order/<order_id>/pay', methods=['GET'])
@login_required
def pay_order(order_id):
    """Redirect to the new instant checkout page."""
    return redirect(url_for('payment.checkout', order_id=order_id))


# ── COD CONFIRMATION ────────────────────────────────────────────────────────

@payment_bp.route('/order/<order_id>/confirm-cod', methods=['POST'])
@login_required
def confirm_order_cod(order_id):
    """Confirm Cash on Delivery for a material order."""
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

        if order_data.get('payment_status') in ('paid', 'cod_confirmed', 'card_pending'):
            return jsonify({'success': False, 'message': 'Payment already confirmed for this order'}), 400

        receipt_number = _generate_receipt_number()

        # Delivery details sent from checkout page
        data_body       = request.get_json(silent=True) or {}
        delivery_date   = data_body.get('delivery_date', '')
        delivery_slot   = data_body.get('delivery_slot', '')
        delivery_phone  = data_body.get('delivery_phone', '')
        delivery_notes  = data_body.get('delivery_notes', '')

        order_ref.update({
            'payment_status':       'cod_confirmed',
            'payment_method':       'cash_on_delivery',
            'receipt_number':       receipt_number,
            'payment_confirmed_at': datetime.now(),
            'status':               'processing',
            'delivery_date':        delivery_date,
            'delivery_slot':        delivery_slot,
            'delivery_phone':       delivery_phone,
            'delivery_notes':       delivery_notes,
            'updated_at':           datetime.now()
        })

        # Store payment record
        db.collection('payments').add({
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
        })

        # Notify supplier
        supplier_id = order_data.get('supplier_id')
        if supplier_id:
            _create_notification(
                supplier_id,
                'New Order Received — COD',
                f'{current_user.name} placed an order with Cash on Delivery. '
                f'Amount: ₹{order_data.get("total", 0):,.0f}. '
                f'Order #{order_id[:8].upper()}',
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


# ── CARD PAYMENT DECLARATION ─────────────────────────────────────────────────

@payment_bp.route('/order/<order_id>/declare-card', methods=['POST'])
@login_required
def declare_order_card(order_id):
    """
    User declares they have paid via card (demo/fake payment).
    Sets payment_status = 'card_pending' so the supplier can verify on delivery.
    """
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

        if order_data.get('payment_status') in ('paid', 'cod_confirmed', 'card_pending'):
            return jsonify({'success': False, 'message': 'Payment already confirmed for this order'}), 400

        data        = request.get_json(silent=True) or {}
        card_last4  = (data.get('card_last4') or '').strip()
        card_txn_id = (data.get('card_txn_id') or '').strip()
        delivery_date  = data.get('delivery_date', '')
        delivery_slot  = data.get('delivery_slot', '')
        delivery_phone = data.get('delivery_phone', '')
        delivery_notes = data.get('delivery_notes', '')

        receipt_number = _generate_receipt_number()

        update_payload = {
            'payment_status':        'card_pending',
            'payment_method':        'card',
            'receipt_number':        receipt_number,
            'payment_declared_at':   datetime.now(),
            'status':                'processing',
            'delivery_date':         delivery_date,
            'delivery_slot':         delivery_slot,
            'delivery_phone':        delivery_phone,
            'delivery_notes':        delivery_notes,
            'updated_at':            datetime.now()
        }
        if card_last4:
            update_payload['card_last4']  = card_last4
        if card_txn_id:
            update_payload['card_txn_id'] = card_txn_id

        order_ref.update(update_payload)

        # Store payment record
        payment_doc = {
            'type':           'material_order',
            'order_id':       order_id,
            'user_id':        current_user.id,
            'user_name':      current_user.name,
            'supplier_id':    order_data.get('supplier_id'),
            'supplier_name':  order_data.get('supplier_name'),
            'amount':         order_data.get('total', 0),
            'method':         'card',
            'status':         'card_pending',
            'receipt_number': receipt_number,
            'project_title':  order_data.get('project_title', ''),
            'created_at':     datetime.now()
        }
        if card_last4:
            payment_doc['card_last4']  = card_last4
        if card_txn_id:
            payment_doc['card_txn_id'] = card_txn_id
        db.collection('payments').add(payment_doc)

        # Notify supplier
        supplier_id = order_data.get('supplier_id')
        if supplier_id:
            msg = (
                f'{current_user.name} paid via card for Order #{order_id[:8].upper()}. '
                f'Amount: ₹{order_data.get("total", 0):,.0f}. '
            )
            if card_last4:
                msg += f'Card ending ···· {card_last4}. '
            msg += 'Please verify on delivery.'
            _create_notification(
                supplier_id,
                'New Order Received — Card Payment',
                msg,
                'payment',
                f'/supplier/order/{order_id}'
            )

        return jsonify({
            'success':        True,
            'message':        'Card payment recorded successfully!',
            'receipt_number': receipt_number,
            'redirect_url':   url_for('payment.order_receipt', order_id=order_id)
        })

    except Exception as e:
        print(f"Card declare error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


# ── ORDER RECEIPT ────────────────────────────────────────────────────────────

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
#  CONTRACTOR PAYMENT  (COD only)
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

        project_ref.update({
            'contractor_payment_status':       'cod_confirmed',
            'contractor_payment_method':       'cash_on_delivery',
            'contractor_receipt_number':       receipt_number,
            'contractor_payment_confirmed_at': datetime.now(),
            'updated_at':                      datetime.now()
        })

        db.collection('payments').add({
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
        })

        _create_notification(
            contractor_id,
            'Payment Confirmed (COD)',
            f'{current_user.name} confirmed Cash on Delivery payment of '
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

        total_spent = sum(
            p.get('amount', 0)
            for p in payments
            if p.get('status') in ('paid', 'cod_confirmed', 'card_pending')
        )

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
#  SUPPLIER: mark order as cash collected / card verified on delivery
#  ✅ FIX: now also deducts material stock when payment is confirmed
# ─────────────────────────────────────────────────────────────────────────────

@payment_bp.route('/supplier/order/<order_id>/collect-cash', methods=['POST'])
@login_required
def supplier_collect_cash(order_id):
    """
    Supplier marks cash collected or card payment verified on delivery.
    Also deducts stock for each delivered material item.
    """
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

        # Mark order as paid and completed
        order_ref.update({
            'payment_status':    'paid',
            'cash_collected_at': datetime.now(),
            'status':            'completed',
            'updated_at':        datetime.now()
        })

        # ✅ Deduct stock for all delivered materials
        order_items = order_data.get('items') or order_data.get('order_items') or []
        _deduct_stock(db, order_items)

        # Update payment record status too
        payments_ref = db.collection('payments') \
            .where('order_id', '==', order_id) \
            .stream()
        for pdoc in payments_ref:
            db.collection('payments').document(pdoc.id).update({'status': 'paid'})

        # Notify customer
        user_id = order_data.get('user_id')
        if user_id:
            method = order_data.get('payment_method', '')
            method_label = 'Card payment verified' if method == 'card' else 'Cash collected'
            _create_notification(
                user_id,
                f'{method_label} — Order Complete',
                f'Your order #{order_id[:8].upper()} has been delivered and payment confirmed. '
                f'Amount: ₹{order_data.get("total", 0):,.0f}',
                'payment',
                '/user/my-orders'
            )

        return jsonify({'success': True, 'message': 'Payment confirmed and order marked as completed!'})

    except Exception as e:
        print(f"Collect cash error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500