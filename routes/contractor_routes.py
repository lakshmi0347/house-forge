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

def get_db():
    """Get database instance"""
    try:
        return firestore.client()
    except Exception as e:
        print(f"Error getting database: {e}")
        return None


# ─── HELPER: fetch contractor profile picture ────────────────────────────────
def _get_contractor_pic(db, contractor_id):
    try:
        doc = db.collection('contractors').document(contractor_id).get()
        if doc.exists:
            return doc.to_dict().get('profile_picture')
    except Exception:
        pass
    return None


@contractor_bp.route('/dashboard')
@login_required
def dashboard():
    """Contractor Dashboard - Main page after login"""
    db = get_db()

    # ── Bids submitted by this contractor ────────────────────────────────────
    bids_ref = db.collection('bids').where('contractor_id', '==', current_user.id).stream()
    bids = []
    for doc in bids_ref:
        bid_data = doc.to_dict()
        bid_data['id'] = doc.id
        bids.append(bid_data)

    # ── Active projects ───────────────────────────────────────────────────────
    active_projects_ref = (
        db.collection('projects')
          .where('contractor_id', '==', current_user.id)
          .where('status', '==', 'active')
          .stream()
    )
    active_projects = []
    for doc in active_projects_ref:
        project_data = doc.to_dict()
        project_data['id'] = doc.id
        active_projects.append(project_data)

    # ── Completed projects count (from Firestore, NOT from current_user) ─────
    completed_projects_ref = (
        db.collection('projects')
          .where('contractor_id', '==', current_user.id)
          .where('status', '==', 'completed')
          .stream()
    )
    completed_count = len(list(completed_projects_ref))

    # ── Available projects (planning, no accepted bid) ────────────────────────
    available_projects_ref = (
        db.collection('projects')
          .where('status', '==', 'planning')
          .limit(10)
          .stream()
    )
    available_projects = []
    for doc in available_projects_ref:
        project_data = doc.to_dict()
        project_data['id'] = doc.id
        available_projects.append(project_data)

    # ── Contractor rating from Firestore ──────────────────────────────────────
    rating = 0.0
    verified = False
    try:
        con_doc = db.collection('contractors').document(current_user.id).get()
        if con_doc.exists:
            con_data = con_doc.to_dict()
            rating = con_data.get('rating', 0.0)
            verified = con_data.get('active', False)
    except Exception:
        pass

    stats = {
        'total_estimates':    len(bids),
        'active_projects':    len(active_projects),
        'completed_projects': completed_count,          # ← fixed
        'rating':             rating,                   # ← fixed
        'verified':           verified,                 # ← fixed
    }

    contractor_profile_picture = _get_contractor_pic(db, current_user.id)

    # Sort bids newest first, take top 5
    bids.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)

    return render_template(
        'contractor/dashboard.html',
        estimates=bids[:5],
        active_projects=active_projects,
        available_projects=available_projects[:5],
        stats=stats,
        contractor_profile_picture=contractor_profile_picture,   # ← was missing
    )


@contractor_bp.route('/profile')
@login_required
def profile():
    """Contractor Profile Page"""
    db = get_db()

    try:
        contractor_ref = db.collection('contractors').document(current_user.id)
        contractor_doc = contractor_ref.get()

        if not contractor_doc.exists:
            flash('Contractor profile not found. Please contact support.', 'error')
            return redirect(url_for('contractor.dashboard'))

        contractor_data = contractor_doc.to_dict()

        # Convert Firebase datetime to string
        if 'created_at' in contractor_data and contractor_data['created_at']:
            try:
                contractor_data['created_at'] = contractor_data['created_at'].strftime('%Y-%m-%d')
            except Exception:
                contractor_data['created_at'] = 'N/A'
        else:
            contractor_data['created_at'] = 'N/A'

        contractor_data['years_experience'] = contractor_data.get('experience', 0)
        contractor_data['verified'] = contractor_data.get('active', False)

        # ── Active projects count ─────────────────────────────────────────────
        try:
            active_qs = (
                db.collection('projects')
                  .where('contractor_id', '==', current_user.id)
                  .where('status', '==', 'active')
                  .stream()
            )
            active_projects_count = len(list(active_qs))
        except Exception as e:
            print(f"Error counting active projects: {e}")
            active_projects_count = 0

        # ── Completed projects count (for the stat widget on profile) ─────────
        try:
            completed_qs = (
                db.collection('projects')
                  .where('contractor_id', '==', current_user.id)
                  .where('status', '==', 'completed')
                  .stream()
            )
            completed_projects_count = len(list(completed_qs))
            # Override whatever is stored; keep the live count authoritative
            contractor_data['completed_projects'] = completed_projects_count
        except Exception as e:
            print(f"Error counting completed projects: {e}")
            # Fall back to stored value
            contractor_data.setdefault('completed_projects', 0)

        # Set defaults
        contractor_data.setdefault('name', '')
        contractor_data.setdefault('email', '')
        contractor_data.setdefault('company_name', '')
        contractor_data.setdefault('phone', '')
        contractor_data.setdefault('location', '')
        contractor_data.setdefault('bio', '')
        contractor_data.setdefault('license_number', '')
        contractor_data.setdefault('specializations', [])
        contractor_data.setdefault('rating', 0.0)
        contractor_data.setdefault('profile_picture', '')

        contractor_profile_picture = contractor_data.get('profile_picture') or None

        return render_template(
            'contractor/profile.html',
            contractor_data=contractor_data,
            active_projects_count=active_projects_count,
            contractor_profile_picture=contractor_profile_picture,  # ← was missing
        )

    except Exception as e:
        print(f"EXCEPTION IN PROFILE ROUTE: {e}")
        import traceback
        traceback.print_exc()
        flash('An error occurred while loading your profile', 'error')
        return redirect(url_for('contractor.dashboard'))


@contractor_bp.route('/my-projects')
@login_required
def my_projects():
    """View active and completed projects assigned to this contractor"""
    db = get_db()

    projects_ref = (
        db.collection('projects')
          .where('contractor_id', '==', current_user.id)
          .stream()
    )

    projects = []           # active / planning
    completed_projects = [] # completed

    for doc in projects_ref:
        project_data = doc.to_dict()
        project_data['id'] = doc.id
        if project_data.get('status') == 'completed':
            completed_projects.append(project_data)
        else:
            projects.append(project_data)

    contractor_profile_picture = _get_contractor_pic(db, current_user.id)

    return render_template(
        'contractor/active_projects.html',
        projects=projects,
        completed_projects=completed_projects,
        contractor_profile_picture=contractor_profile_picture,
    )


@contractor_bp.route('/project/<project_id>/complete', methods=['POST'])
@login_required
def complete_project(project_id):
    """Mark project as completed"""
    db = get_db()
    try:
        project_ref = db.collection('projects').document(project_id)
        project_doc = project_ref.get()

        if not project_doc.exists:
            return jsonify({'success': False, 'message': 'Project not found'}), 404

        project_data = project_doc.to_dict()

        if project_data.get('contractor_id') != current_user.id:
            return jsonify({'success': False, 'message': 'Access denied'}), 403

        if project_data.get('status') == 'completed':
            return jsonify({'success': False, 'message': 'Project is already completed'}), 400

        project_ref.update({
            'status':       'completed',
            'completed_at': datetime.now(),
            'updated_at':   datetime.now(),
        })

        # ── Keep the denormalised counter on the contractor document in sync ──
        try:
            con_ref = db.collection('contractors').document(current_user.id)
            con_doc = con_ref.get()
            if con_doc.exists:
                current_count = con_doc.to_dict().get('completed_projects', 0) or 0
                con_ref.update({'completed_projects': current_count + 1})
        except Exception as ce:
            print(f"Warning: could not update completed_projects counter: {ce}")

        return jsonify({'success': True, 'message': 'Project completed successfully!'})

    except Exception as e:
        print(f"Error completing project: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# All remaining routes below are UNCHANGED from the original file.
# Copy them in as-is after the four functions above.
# ─────────────────────────────────────────────────────────────────────────────

@contractor_bp.route('/update_business_info', methods=['POST'])
@login_required
def update_business_info():
    db = get_db()
    try:
        company_name    = request.form.get('company_name')
        license_number  = request.form.get('license_number', '')
        years_experience = int(request.form.get('years_experience', 0))
        phone           = request.form.get('phone')
        location        = request.form.get('location')
        bio             = request.form.get('bio', '')
        specializations = json.loads(request.form.get('specializations', '[]'))

        db.collection('contractors').document(current_user.id).update({
            'company_name':   company_name,
            'license_number': license_number,
            'experience':     years_experience,
            'phone':          phone,
            'location':       location,
            'bio':            bio,
            'specializations': specializations,
            'updated_at':     datetime.now(),
        })
        return jsonify({'success': True, 'message': 'Business information updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@contractor_bp.route('/update_personal_info', methods=['POST'])
@login_required
def update_personal_info():
    db = get_db()
    try:
        name  = request.form.get('name')
        email = request.form.get('email')
        db.collection('contractors').document(current_user.id).update({
            'name':       name,
            'email':      email,
            'updated_at': datetime.now(),
        })
        return jsonify({'success': True, 'message': 'Personal information updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@contractor_bp.route('/upload_profile_picture', methods=['POST'])
@login_required
def upload_profile_picture():
    db = get_db()
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

        filename = secure_filename(
            f"contractor_{current_user.id}_{int(datetime.now().timestamp())}.{file_ext}"
        )
        upload_folder = os.path.join('static', 'uploads', 'profiles')
        os.makedirs(upload_folder, exist_ok=True)
        file.save(os.path.join(upload_folder, filename))

        db.collection('contractors').document(current_user.id).update({
            'profile_picture': filename,
            'updated_at':      datetime.now(),
        })
        return jsonify({'success': True, 'message': 'Profile picture uploaded successfully', 'filename': filename})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@contractor_bp.route('/change_password', methods=['POST'])
@login_required
def change_password():
    db = get_db()
    try:
        current_password = request.form.get('currentPassword')
        new_password     = request.form.get('newPassword')

        contractor_doc = db.collection('contractors').document(current_user.id).get()
        if not contractor_doc.exists:
            return jsonify({'success': False, 'message': 'Contractor not found'}), 404

        contractor_data = contractor_doc.to_dict()
        if not check_password_hash(contractor_data.get('password', ''), current_password):
            return jsonify({'success': False, 'message': 'Current password is incorrect'}), 400

        db.collection('contractors').document(current_user.id).update({
            'password':   generate_password_hash(new_password),
            'updated_at': datetime.now(),
        })
        return jsonify({'success': True, 'message': 'Password changed successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@contractor_bp.route('/browse-projects')
@login_required
def browse_projects():
    db = get_db()
    if not db:
        flash('Database connection error', 'error')
        return redirect(url_for('contractor.dashboard'))

    try:
        projects_ref = db.collection('projects').stream()

        my_bids_ref = (
            db.collection('bids')
              .where('contractor_id', '==', current_user.id)
              .stream()
        )
        my_bid_project_ids = {bid.to_dict().get('project_id') for bid in my_bids_ref}

        projects = []
        for doc in projects_ref:
            project_data = doc.to_dict()
            project_id   = doc.id

            if project_data.get('status') != 'planning':
                continue

            accepted_bids = list(
                db.collection('bids')
                  .where('project_id', '==', project_id)
                  .where('status',     '==', 'accepted')
                  .stream()
            )
            if len(accepted_bids) > 0:
                continue

            project_data['id']      = project_id
            project_data['has_bid'] = project_id in my_bid_project_ids
            projects.append(project_data)

        projects.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)

        contractor_profile_picture = _get_contractor_pic(db, current_user.id)

        return render_template(
            'contractor/browse_projects.html',
            projects=projects,
            contractor_profile_picture=contractor_profile_picture,
        )

    except Exception as e:
        flash(f'Error loading projects: {str(e)}', 'error')
        return redirect(url_for('contractor.dashboard'))


@contractor_bp.route('/project/<project_id>/view')
@login_required
def view_project(project_id):
    db = get_db()
    try:
        project_doc = db.collection('projects').document(project_id).get()
        if not project_doc.exists:
            flash('Project not found', 'error')
            return redirect(url_for('contractor.browse_projects'))

        project_data       = project_doc.to_dict()
        project_data['id'] = project_id

        user_doc = db.collection('users').document(project_data.get('user_id')).get()
        if user_doc.exists:
            u = user_doc.to_dict()
            project_data['user_name']  = u.get('name',  'Unknown')
            project_data['user_phone'] = u.get('phone', 'N/A')
            project_data['user_email'] = u.get('email', 'N/A')

        existing_bid_docs = list(
            db.collection('bids')
              .where('project_id',    '==', project_id)
              .where('contractor_id', '==', current_user.id)
              .limit(1)
              .stream()
        )
        project_data['has_bid'] = len(existing_bid_docs) > 0
        if project_data['has_bid']:
            bid_doc = existing_bid_docs[0]
            project_data['existing_bid']       = bid_doc.to_dict()
            project_data['existing_bid']['id'] = bid_doc.id

        contractor_profile_picture = _get_contractor_pic(db, current_user.id)
        estimation = project_data.get('estimation', {})

        return render_template(
            'contractor/view_project_detail.html',
            project=project_data,
            estimation=estimation,
            contractor_profile_picture=contractor_profile_picture,
        )

    except Exception as e:
        flash(f'Error loading project: {str(e)}', 'error')
        return redirect(url_for('contractor.browse_projects'))


@contractor_bp.route('/project/<project_id>/submit-bid', methods=['GET', 'POST'])
@login_required
def submit_bid(project_id):
    db = get_db()

    if request.method == 'POST':
        try:
            if not current_user.verified:
                flash('Only verified contractors can submit bids', 'error')
                return redirect(url_for('contractor.browse_projects'))

            existing_bid = list(
                db.collection('bids')
                  .where('project_id',    '==', project_id)
                  .where('contractor_id', '==', current_user.id)
                  .limit(1)
                  .stream()
            )
            if len(existing_bid) > 0:
                flash('You have already submitted a bid for this project', 'error')
                return redirect(url_for('contractor.browse_projects'))

            total_cost      = float(request.form.get('total_cost'))
            duration_months = int(request.form.get('duration_months'))
            proposal        = request.form.get('proposal')
            material_cost   = float(request.form.get('material_cost', 0))
            labor_cost      = float(request.form.get('labor_cost', 0))
            other_cost      = float(request.form.get('other_cost', 0))

            project_doc  = db.collection('projects').document(project_id).get()
            project_data = project_doc.to_dict()

            bid_data = {
                'project_id':           project_id,
                'project_title':        project_data.get('title', 'Untitled Project'),
                'user_id':              project_data.get('user_id'),
                'contractor_id':        current_user.id,
                'contractor_name':      current_user.name,
                'contractor_company':   getattr(current_user, 'company_name', current_user.name),
                'contractor_rating':    getattr(current_user, 'rating', 0.0),
                'contractor_experience': getattr(current_user, 'experience', 0),
                'total_cost':           total_cost,
                'material_cost':        material_cost,
                'labor_cost':           labor_cost,
                'other_cost':           other_cost,
                'duration_months':      duration_months,
                'proposal':             proposal,
                'status':               'pending',
                'created_at':           datetime.now(),
                'updated_at':           datetime.now(),
            }
            db.collection('bids').add(bid_data)

            flash('Bid submitted successfully! The project owner will review it.', 'success')
            return redirect(url_for('contractor.my_bids'))

        except Exception as e:
            flash(f'Error submitting bid: {str(e)}', 'error')
            return redirect(url_for('contractor.browse_projects'))

    # GET
    try:
        project_doc = db.collection('projects').document(project_id).get()
        if not project_doc.exists:
            flash('Project not found', 'error')
            return redirect(url_for('contractor.browse_projects'))

        project       = project_doc.to_dict()
        project['id'] = project_doc.id

        existing_bid = list(
            db.collection('bids')
              .where('project_id',    '==', project_id)
              .where('contractor_id', '==', current_user.id)
              .limit(1)
              .stream()
        )
        if len(existing_bid) > 0:
            flash('You have already submitted a bid for this project', 'error')
            return redirect(url_for('contractor.browse_projects'))

        return render_template('contractor/submit_bid.html', project=project)

    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('contractor.browse_projects'))


@contractor_bp.route('/my-bids')
@login_required
def my_bids():
    db = get_db()
    try:
        bids_ref = db.collection('bids').where('contractor_id', '==', current_user.id).stream()
        bids = []
        for doc in bids_ref:
            bid_data       = doc.to_dict()
            bid_data['id'] = doc.id
            bids.append(bid_data)

        bids.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)

        stats = {
            'total':    len(bids),
            'pending':  len([b for b in bids if b.get('status') == 'pending']),
            'accepted': len([b for b in bids if b.get('status') == 'accepted']),
            'rejected': len([b for b in bids if b.get('status') == 'rejected']),
        }

        contractor_profile_picture = _get_contractor_pic(db, current_user.id)

        return render_template(
            'contractor/my_bids.html',
            bids=bids,
            stats=stats,
            contractor_profile_picture=contractor_profile_picture,
        )

    except Exception as e:
        flash(f'Error loading bids: {str(e)}', 'error')
        return redirect(url_for('contractor.dashboard'))


@contractor_bp.route('/bid/<bid_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_bid(bid_id):
    db = get_db()
    try:
        bid_doc = db.collection('bids').document(bid_id).get()
        if not bid_doc.exists:
            flash('Bid not found', 'error')
            return redirect(url_for('contractor.my_bids'))

        bid_data = bid_doc.to_dict()
        if bid_data.get('contractor_id') != current_user.id:
            flash('Access denied', 'error')
            return redirect(url_for('contractor.my_bids'))

        if bid_data.get('status') != 'pending':
            flash('Cannot edit accepted or rejected bids', 'error')
            return redirect(url_for('contractor.my_bids'))

        if request.method == 'POST':
            updated_data = {
                'total_cost':    float(request.form.get('total_cost')),
                'material_cost': float(request.form.get('material_cost', 0)),
                'labor_cost':    float(request.form.get('labor_cost', 0)),
                'other_cost':    float(request.form.get('other_cost', 0)),
                'duration_days': int(request.form.get('duration_days')),
                'proposal':      request.form.get('proposal'),
                'updated_at':    datetime.now(),
            }
            db.collection('bids').document(bid_id).update(updated_data)
            flash('Bid updated successfully!', 'success')
            return redirect(url_for('contractor.my_bids'))

        bid_data['id'] = bid_id
        project_doc    = db.collection('projects').document(bid_data.get('project_id')).get()
        project        = project_doc.to_dict() if project_doc.exists else {}
        project['id']  = bid_data.get('project_id')

        return render_template('contractor/submit_bid.html', bid=bid_data, project=project, edit_mode=True)

    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('contractor.my_bids'))


@contractor_bp.route('/bid/<bid_id>/delete', methods=['POST'])
@login_required
def delete_bid(bid_id):
    db = get_db()
    try:
        bid_doc = db.collection('bids').document(bid_id).get()
        if not bid_doc.exists:
            flash('Bid not found', 'error')
            return redirect(url_for('contractor.my_bids'))

        bid_data = bid_doc.to_dict()
        if bid_data.get('contractor_id') != current_user.id:
            flash('Access denied', 'error')
            return redirect(url_for('contractor.my_bids'))

        if bid_data.get('status') != 'pending':
            flash('Cannot delete accepted or rejected bids', 'error')
            return redirect(url_for('contractor.my_bids'))

        db.collection('bids').document(bid_id).delete()
        flash('Bid deleted successfully', 'success')

    except Exception as e:
        flash(f'Error deleting bid: {str(e)}', 'error')

    return redirect(url_for('contractor.my_bids'))


# ======================== MESSAGING ROUTES ========================

@contractor_bp.route('/messages')
@login_required
def messages():
    return render_template('contractor/messages.html')


@contractor_bp.route('/api/conversations')
@login_required
def api_conversations():
    try:
        messages_ref = db.collection('messages').where('contractor_id', '==', current_user.id).stream()
        conversations = {}

        for doc in messages_ref:
            message_data = doc.to_dict()
            if (message_data.get('sender_id') == current_user.id
                    and message_data.get('sender_type') == 'contractor'):
                continue

            user_id = message_data.get('user_id')
            if not user_id:
                continue

            conv_key = f"user_{user_id}"
            if conv_key not in conversations:
                conversations[conv_key] = {
                    'user_id':          user_id,
                    'sender_name':      message_data.get('sender_name', 'Customer'),
                    'sender_email':     message_data.get('sender_email', ''),
                    'sender_phone':     message_data.get('sender_phone', ''),
                    'last_message':     message_data.get('message', ''),
                    'last_message_time': message_data.get('created_at'),
                    'unread_count':     0,
                }

            if message_data.get('created_at') > conversations[conv_key]['last_message_time']:
                conversations[conv_key]['last_message']      = message_data.get('message', '')
                conversations[conv_key]['last_message_time'] = message_data.get('created_at')

            if (not message_data.get('read', False)
                    and message_data.get('sender_type') != 'contractor'):
                conversations[conv_key]['unread_count'] += 1

        conversations_list = list(conversations.values())
        conversations_list.sort(key=lambda x: x.get('last_message_time', datetime.min), reverse=True)
        return jsonify({'conversations': conversations_list})

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback; traceback.print_exc()
        return jsonify({'conversations': []})


@contractor_bp.route('/api/messages/<user_id>')
@login_required
def api_messages(user_id):
    try:
        all_messages = []
        messages_ref = (
            db.collection('messages')
              .where('contractor_id', '==', current_user.id)
              .where('user_id',       '==', user_id)
              .stream()
        )

        for doc in messages_ref:
            msg        = doc.to_dict()
            msg['id']  = doc.id
            msg['direction'] = (
                'outgoing'
                if msg.get('sender_id') == current_user.id and msg.get('sender_type') == 'contractor'
                else 'incoming'
            )
            all_messages.append(msg)

        all_messages.sort(key=lambda x: x.get('created_at', datetime.min))

        user_doc = db.collection('users').document(user_id).get()
        user_info = (
            {
                'name':  user_doc.to_dict().get('name', 'Customer'),
                'email': user_doc.to_dict().get('email', ''),
                'phone': user_doc.to_dict().get('phone', ''),
            }
            if user_doc.exists
            else {'name': 'Customer', 'email': '', 'phone': ''}
        )

        for msg in all_messages:
            if msg['direction'] == 'incoming' and not msg.get('read', False):
                db.collection('messages').document(msg['id']).update({
                    'read':    True,
                    'read_at': datetime.now(),
                })

        return jsonify({'messages': all_messages, 'user_info': user_info})

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback; traceback.print_exc()
        return jsonify({'messages': [], 'user_info': {}})


@contractor_bp.route('/messages/send/<user_id>', methods=['POST'])
@login_required
def send_chat_message(user_id):
    try:
        message_text = request.form.get('message', '').strip()
        if not message_text:
            return jsonify({'success': False, 'message': 'Message cannot be empty'}), 400

        message_data = {
            'user_id':       user_id,
            'contractor_id': current_user.id,
            'sender_id':     current_user.id,
            'sender_type':   'contractor',
            'sender_name':   getattr(current_user, 'company_name', None) or current_user.name,
            'sender_email':  getattr(current_user, 'email', ''),
            'sender_phone':  getattr(current_user, 'phone', ''),
            'message':       message_text,
            'type':          'chat',
            'read':          False,
            'created_at':    datetime.now(),
        }
        doc_ref    = db.collection('messages').add(message_data)
        message_id = doc_ref[1].id

        return jsonify({
            'success':    True,
            'message_id': message_id,
            'timestamp':  datetime.now().strftime('%I:%M %p'),
        })

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@contractor_bp.route('/messages/unread-count')
@login_required
def messages_unread_count():
    try:
        db_local = get_db()
        if not db_local:
            return jsonify({'count': 0}), 200

        messages_ref  = db_local.collection('messages').where('contractor_id', '==', current_user.id).stream()
        unread_count  = 0
        for doc in messages_ref:
            message_data = doc.to_dict()
            if (message_data.get('sender_id') == current_user.id
                    and message_data.get('sender_type') == 'contractor'):
                continue
            if not message_data.get('read', False):
                unread_count += 1

        response = jsonify({'count': unread_count})
        response.headers['Content-Type'] = 'application/json'
        return response, 200

    except Exception as e:
        print(f"Error getting unread count: {str(e)}")
        import traceback; traceback.print_exc()
        response = jsonify({'count': 0, 'error': str(e)})
        response.headers['Content-Type'] = 'application/json'
        return response, 200


@contractor_bp.route('/user/<user_id>/profile')
@login_required
def user_profile(user_id):
    db = get_db()
    try:
        user_doc = db.collection('users').document(user_id).get()
        if not user_doc.exists:
            flash('User not found', 'error')
            return redirect(url_for('contractor.dashboard'))

        user_data       = user_doc.to_dict()
        user_data['id'] = user_id

        assigned_projects_ref = (
            db.collection('projects')
              .where('user_id',       '==', user_id)
              .where('contractor_id', '==', current_user.id)
              .stream()
        )
        assigned_projects = []
        for doc in assigned_projects_ref:
            p       = doc.to_dict()
            p['id'] = doc.id
            assigned_projects.append(p)

        bids_ref = (
            db.collection('bids')
              .where('contractor_id', '==', current_user.id)
              .where('user_id',       '==', user_id)
              .stream()
        )
        bid_project_ids = {b.to_dict().get('project_id') for b in bids_ref}

        bid_projects = []
        for project_id in bid_project_ids:
            if any(p['id'] == project_id for p in assigned_projects):
                continue
            pdoc = db.collection('projects').document(project_id).get()
            if pdoc.exists:
                p       = pdoc.to_dict()
                p['id'] = project_id
                bid_projects.append(p)

        all_projects = assigned_projects + bid_projects

        if 'created_at' in user_data and user_data['created_at']:
            try:
                user_data['created_at'] = user_data['created_at'].strftime('%B %d, %Y')
            except Exception:
                user_data['created_at'] = 'N/A'
        else:
            user_data['created_at'] = 'N/A'

        user_data.setdefault('name', 'User')
        user_data.setdefault('email', 'N/A')
        user_data.setdefault('phone', 'N/A')
        user_data.setdefault('location', 'N/A')
        user_data.setdefault('profile_picture', '')

        stats = {
            'total_projects':     len(all_projects),
            'active_projects':    len([p for p in all_projects if p.get('status') == 'active']),
            'completed_projects': len([p for p in all_projects if p.get('status') == 'completed']),
        }

        return render_template(
            'contractor/user_profile.html',
            user_data=user_data,
            projects=all_projects,
            stats=stats,
        )

    except Exception as e:
        print(f"Error loading user profile: {e}")
        import traceback; traceback.print_exc()
        flash('Error loading user profile', 'error')
        return redirect(url_for('contractor.dashboard'))


@contractor_bp.route('/edit-profile')
@login_required
def edit_profile():
    db = get_db()
    try:
        contractor_doc = db.collection('contractors').document(current_user.id).get()
        if not contractor_doc.exists:
            flash('Contractor profile not found', 'error')
            return redirect(url_for('contractor.profile'))

        contractor_data = contractor_doc.to_dict()

        if 'created_at' in contractor_data and contractor_data['created_at']:
            try:
                contractor_data['created_at'] = contractor_data['created_at'].strftime('%Y-%m-%d')
            except Exception:
                contractor_data['created_at'] = 'N/A'

        contractor_data.setdefault('name', '')
        contractor_data.setdefault('email', '')
        contractor_data.setdefault('company_name', '')
        contractor_data.setdefault('phone', '')
        contractor_data.setdefault('location', '')
        contractor_data.setdefault('bio', '')
        contractor_data.setdefault('license_number', '')
        contractor_data.setdefault('specializations', [])
        contractor_data.setdefault('years_experience', 0)
        contractor_data.setdefault('profile_picture', '')

        contractor_profile_picture = contractor_data.get('profile_picture') or None

        return render_template(
            'contractor/edit_profile.html',
            contractor_data=contractor_data,
            contractor_profile_picture=contractor_profile_picture,
        )

    except Exception as e:
        print(f"Error loading edit profile: {e}")
        flash('An error occurred while loading your profile', 'error')
        return redirect(url_for('contractor.profile'))