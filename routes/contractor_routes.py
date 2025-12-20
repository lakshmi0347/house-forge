from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from firebase_admin import firestore
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import json

contractor_bp = Blueprint('contractor', __name__)

def get_db():
    """Get database instance"""
    try:
        return firestore.client()
    except Exception as e:
        print(f"Error getting database: {e}")
        return None

@contractor_bp.route('/dashboard')
@login_required
def dashboard():
    """Contractor Dashboard - Main page after login"""
    db = get_db()
    
    # Get contractor's submitted bids
    bids_ref = db.collection('bids').where('contractor_id', '==', current_user.id).stream()
    bids = []
    for doc in bids_ref:
        bid_data = doc.to_dict()
        bid_data['id'] = doc.id
        bids.append(bid_data)
    
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
        'total_estimates': len(bids),
        'active_projects': len(active_projects),
        'completed_projects': current_user.completed_projects if hasattr(current_user, 'completed_projects') else 0,
        'rating': current_user.rating if hasattr(current_user, 'rating') else 0.0,
        'verified': current_user.verified if hasattr(current_user, 'verified') else False
    }
    
    return render_template('contractor/dashboard.html',
                         estimates=bids[:5],
                         active_projects=active_projects,
                         available_projects=available_projects[:5],
                         stats=stats)

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
        except Exception as e:
            print(f"Error counting projects: {e}")
            active_projects_count = 0
        
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
        contractor_data.setdefault('completed_projects', 0)
        contractor_data.setdefault('profile_picture', '')
        
        return render_template('contractor/profile.html',
                             contractor_data=contractor_data,
                             active_projects_count=active_projects_count)
    
    except Exception as e:
        print(f"EXCEPTION IN PROFILE ROUTE: {e}")
        import traceback
        traceback.print_exc()
        flash('An error occurred while loading your profile', 'error')
        return redirect(url_for('contractor.dashboard'))

@contractor_bp.route('/update_business_info', methods=['POST'])
@login_required
def update_business_info():
    """Update contractor business information"""
    db = get_db()
    
    try:
        company_name = request.form.get('company_name')
        license_number = request.form.get('license_number', '')
        years_experience = int(request.form.get('years_experience', 0))
        phone = request.form.get('phone')
        location = request.form.get('location')
        bio = request.form.get('bio', '')
        specializations = json.loads(request.form.get('specializations', '[]'))
        
        contractor_ref = db.collection('contractors').document(current_user.id)
        contractor_ref.update({
            'company_name': company_name,
            'license_number': license_number,
            'experience': years_experience,
            'phone': phone,
            'location': location,
            'bio': bio,
            'specializations': specializations,
            'updated_at': datetime.now()
        })
        
        return jsonify({'success': True, 'message': 'Business information updated successfully'})
    
    except Exception as e:
        print(f"Error updating business info: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@contractor_bp.route('/update_personal_info', methods=['POST'])
@login_required
def update_personal_info():
    """Update contractor personal information"""
    db = get_db()
    
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        
        contractor_ref = db.collection('contractors').document(current_user.id)
        contractor_ref.update({
            'name': name,
            'email': email,
            'updated_at': datetime.now()
        })
        
        return jsonify({'success': True, 'message': 'Personal information updated successfully'})
    
    except Exception as e:
        print(f"Error updating personal info: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@contractor_bp.route('/upload_profile_picture', methods=['POST'])
@login_required
def upload_profile_picture():
    """Upload contractor profile picture"""
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
        
        filename = secure_filename(f"contractor_{current_user.id}_{int(datetime.now().timestamp())}.{file_ext}")
        
        upload_folder = os.path.join('static', 'uploads', 'profiles')
        os.makedirs(upload_folder, exist_ok=True)
        
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        
        contractor_ref = db.collection('contractors').document(current_user.id)
        contractor_ref.update({
            'profile_picture': filename,
            'updated_at': datetime.now()
        })
        
        return jsonify({'success': True, 'message': 'Profile picture uploaded successfully', 'filename': filename})
    
    except Exception as e:
        print(f"Error uploading profile picture: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@contractor_bp.route('/change_password', methods=['POST'])
@login_required
def change_password():
    """Change contractor password"""
    db = get_db()
    
    try:
        current_password = request.form.get('currentPassword')
        new_password = request.form.get('newPassword')
        
        contractor_ref = db.collection('contractors').document(current_user.id)
        contractor_doc = contractor_ref.get()
        
        if not contractor_doc.exists:
            return jsonify({'success': False, 'message': 'Contractor not found'}), 404
        
        contractor_data = contractor_doc.to_dict()
        
        if not check_password_hash(contractor_data.get('password', ''), current_password):
            return jsonify({'success': False, 'message': 'Current password is incorrect'}), 400
        
        hashed_password = generate_password_hash(new_password)
        contractor_ref.update({
            'password': hashed_password,
            'updated_at': datetime.now()
        })
        
        return jsonify({'success': True, 'message': 'Password changed successfully'})
    
    except Exception as e:
        print(f"Error changing password: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@contractor_bp.route('/browse-projects')
@login_required
def browse_projects():
    """Browse available projects"""
    db = get_db()
    
    try:
        projects_ref = db.collection('projects').where('status', '==', 'planning').stream()
        projects = []
        
        for doc in projects_ref:
            project_data = doc.to_dict()
            project_data['id'] = doc.id
            
            # Get user info
            user_doc = db.collection('users').document(project_data.get('user_id')).get()
            if user_doc.exists:
                project_data['user_name'] = user_doc.to_dict().get('name', 'Unknown')
            
            # Check if contractor already bid
            existing_bid = list(db.collection('bids').where('project_id', '==', doc.id).where('contractor_id', '==', current_user.id).limit(1).stream())
            project_data['has_bid'] = len(existing_bid) > 0
            
            projects.append(project_data)
        
        return render_template('contractor/browse_projects.html', projects=projects)
        
    except Exception as e:
        flash(f'Error loading projects: {str(e)}', 'error')
        return redirect(url_for('contractor.dashboard'))

@contractor_bp.route('/my-projects')
@login_required
def my_projects():
    """View contractor's active projects"""
    db = get_db()
    
    projects_ref = db.collection('projects').where('contractor_id', '==', current_user.id).stream()
    projects = []
    for doc in projects_ref:
        project_data = doc.to_dict()
        project_data['id'] = doc.id
        projects.append(project_data)
    
    return render_template('contractor/active_projects.html', projects=projects)

@contractor_bp.route('/project/<project_id>/view')
@login_required
def view_project(project_id):
    """View project details before bidding"""
    db = get_db()
    
    try:
        project_doc = db.collection('projects').document(project_id).get()
        
        if not project_doc.exists:
            flash('Project not found', 'error')
            return redirect(url_for('contractor.browse_projects'))
        
        project_data = project_doc.to_dict()
        project_data['id'] = project_id
        
        # Get user info
        user_doc = db.collection('users').document(project_data.get('user_id')).get()
        if user_doc.exists:
            project_data['user_name'] = user_doc.to_dict().get('name', 'Unknown')
            project_data['user_phone'] = user_doc.to_dict().get('phone', 'N/A')
            project_data['user_email'] = user_doc.to_dict().get('email', 'N/A')
        
        # Check if contractor already bid
        existing_bid = list(db.collection('bids').where('project_id', '==', project_id).where('contractor_id', '==', current_user.id).limit(1).stream())
        project_data['has_bid'] = len(existing_bid) > 0
        
        if project_data['has_bid']:
            bid_doc = existing_bid[0]
            project_data['existing_bid'] = bid_doc.to_dict()
            project_data['existing_bid']['id'] = bid_doc.id
        
        return render_template('contractor/view_project_detail.html', project=project_data)
        
    except Exception as e:
        flash(f'Error loading project: {str(e)}', 'error')
        return redirect(url_for('contractor.browse_projects'))

@contractor_bp.route('/project/<project_id>/submit-bid', methods=['GET', 'POST'])
@login_required
def submit_bid(project_id):
    """Submit bid for a project"""
    db = get_db()
    
    if request.method == 'POST':
        try:
            # Validate contractor is verified
            if not current_user.verified:
                flash('Only verified contractors can submit bids', 'error')
                return redirect(url_for('contractor.browse_projects'))
            
            # Check if already bid
            existing_bid = list(db.collection('bids').where('project_id', '==', project_id).where('contractor_id', '==', current_user.id).limit(1).stream())
            if len(existing_bid) > 0:
                flash('You have already submitted a bid for this project', 'error')
                return redirect(url_for('contractor.browse_projects'))
            
            # Get form data
            total_cost = float(request.form.get('total_cost'))
            duration_days = int(request.form.get('duration_days'))
            proposal = request.form.get('proposal')
            material_cost = float(request.form.get('material_cost', 0))
            labor_cost = float(request.form.get('labor_cost', 0))
            other_cost = float(request.form.get('other_cost', 0))
            
            # Get project data
            project_doc = db.collection('projects').document(project_id).get()
            project_data = project_doc.to_dict()
            
            # Create bid data
            bid_data = {
                'project_id': project_id,
                'project_title': project_data.get('title', 'Untitled Project'),
                'user_id': project_data.get('user_id'),
                'contractor_id': current_user.id,
                'contractor_name': current_user.name,
                'contractor_company': current_user.company_name if hasattr(current_user, 'company_name') else current_user.name,
                'contractor_rating': current_user.rating if hasattr(current_user, 'rating') else 0.0,
                'contractor_experience': current_user.experience if hasattr(current_user, 'experience') else 0,
                'total_cost': total_cost,
                'material_cost': material_cost,
                'labor_cost': labor_cost,
                'other_cost': other_cost,
                'duration_days': duration_days,
                'proposal': proposal,
                'status': 'pending',
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            
            db.collection('bids').add(bid_data)
            
            flash('Bid submitted successfully! The project owner will review it.', 'success')
            return redirect(url_for('contractor.my_bids'))
            
        except Exception as e:
            flash(f'Error submitting bid: {str(e)}', 'error')
            return redirect(url_for('contractor.browse_projects'))
    
    # GET request
    try:
        project_doc = db.collection('projects').document(project_id).get()
        
        if not project_doc.exists:
            flash('Project not found', 'error')
            return redirect(url_for('contractor.browse_projects'))
        
        project = project_doc.to_dict()
        project['id'] = project_doc.id
        
        # Check if already bid
        existing_bid = list(db.collection('bids').where('project_id', '==', project_id).where('contractor_id', '==', current_user.id).limit(1).stream())
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
    """View all submitted bids"""
    db = get_db()
    
    try:
        bids_ref = db.collection('bids').where('contractor_id', '==', current_user.id).stream()
        bids = []
        
        for doc in bids_ref:
            bid_data = doc.to_dict()
            bid_data['id'] = doc.id
            bids.append(bid_data)
        
        # Sort by created_at descending
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
        
        return render_template('contractor/my_bids.html', bids=bids, stats=stats)
        
    except Exception as e:
        flash(f'Error loading bids: {str(e)}', 'error')
        return redirect(url_for('contractor.dashboard'))

@contractor_bp.route('/bid/<bid_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_bid(bid_id):
    """Edit a pending bid"""
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
                'total_cost': float(request.form.get('total_cost')),
                'material_cost': float(request.form.get('material_cost', 0)),
                'labor_cost': float(request.form.get('labor_cost', 0)),
                'other_cost': float(request.form.get('other_cost', 0)),
                'duration_days': int(request.form.get('duration_days')),
                'proposal': request.form.get('proposal'),
                'updated_at': datetime.now()
            }
            
            db.collection('bids').document(bid_id).update(updated_data)
            flash('Bid updated successfully!', 'success')
            return redirect(url_for('contractor.my_bids'))
        
        bid_data['id'] = bid_id
        
        project_doc = db.collection('projects').document(bid_data.get('project_id')).get()
        project = project_doc.to_dict() if project_doc.exists else {}
        project['id'] = bid_data.get('project_id')
        
        return render_template('contractor/submit_bid.html', bid=bid_data, project=project, edit_mode=True)
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('contractor.my_bids'))

@contractor_bp.route('/bid/<bid_id>/delete', methods=['POST'])
@login_required
def delete_bid(bid_id):
    """Delete a pending bid"""
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
@contractor_bp.route('/messages/unread-count')
@login_required
def unread_messages_count():
    """API endpoint to get unread message count"""
    db = get_db()
    
    try:
        # Get all messages for this contractor (simpler query)
        messages_ref = db.collection('messages').where('contractor_id', '==', current_user.id).stream()
        
        # Count unread in Python instead of Firestore
        count = 0
        for doc in messages_ref:
            if not doc.to_dict().get('read', False):
                count += 1
        
        return jsonify({'count': count})
    except Exception as e:
        print(f"Error in unread count: {str(e)}")
        return jsonify({'count': 0})  
@contractor_bp.route('/messages')
@login_required
def messages():
    """View all messages received by contractor"""
    db = get_db()
    
    try:
        print(f"=" * 50)
        print(f"🔍 Fetching messages for contractor: {current_user.id}")
        print(f"=" * 50)
        
        # Get all messages for this contractor
        messages_ref = db.collection('messages').where('contractor_id', '==', current_user.id).stream()
        messages_list = []
        
        for doc in messages_ref:
            message_data = doc.to_dict()
            message_data['id'] = doc.id
            
            # DEBUG: Print the actual message data
            print(f"\n📨 Message ID: {doc.id}")
            print(f"   Keys in message: {list(message_data.keys())}")
            
            # IMPORTANT: Set default values for all fields to prevent "None" display
            message_data.setdefault('sender_name', 'Unknown Sender')
            message_data.setdefault('sender_email', 'No email provided')
            message_data.setdefault('sender_phone', '')
            message_data.setdefault('subject', 'No subject')
            message_data.setdefault('message', 'No message content')
            message_data.setdefault('type', 'message')
            message_data.setdefault('read', False)
            
            # For quote requests, ensure quote-specific fields exist
            if message_data.get('type') == 'quote_request':
                message_data.setdefault('project_type', 'N/A')
                message_data.setdefault('project_area', 'N/A')
                message_data.setdefault('project_location', 'N/A')
                message_data.setdefault('project_budget', 'N/A')
                message_data.setdefault('project_details', message_data.get('message', 'No details provided'))
            
            # Print actual values after defaults
            print(f"   sender_name: {message_data.get('sender_name')}")
            print(f"   sender_email: {message_data.get('sender_email')}")
            print(f"   subject: {message_data.get('subject')}")
            print(f"   message: {message_data.get('message')[:50] if message_data.get('message') else 'N/A'}...")
            
            # Format created_at for display
            if 'created_at' in message_data and message_data['created_at']:
                try:
                    now = datetime.now()
                    created = message_data['created_at']
                    
                    # Handle if created is a timestamp
                    if hasattr(created, 'timestamp'):
                        created = datetime.fromtimestamp(created.timestamp())
                    
                    diff = now - created
                    
                    if diff.days > 0:
                        message_data['time_ago'] = f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
                    elif diff.seconds // 3600 > 0:
                        hours = diff.seconds // 3600
                        message_data['time_ago'] = f"{hours} hour{'s' if hours > 1 else ''} ago"
                    elif diff.seconds // 60 > 0:
                        minutes = diff.seconds // 60
                        message_data['time_ago'] = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
                    else:
                        message_data['time_ago'] = 'Just now'
                except Exception as e:
                    print(f"⚠️ Error formatting time: {e}")
                    message_data['time_ago'] = 'Recently'
            else:
                message_data['time_ago'] = 'Recently'
            
            messages_list.append(message_data)
        
        print(f"\n✅ Total messages found: {len(messages_list)}")
        
        # Print sample message for debugging
        if messages_list:
            print(f"\n📊 Sample message data structure:")
            sample = messages_list[0]
            for key, value in sample.items():
                if key != 'created_at':  # Skip timestamp objects
                    print(f"   {key}: {repr(value)}")
        
        print(f"=" * 50)
        
        # Sort in Python instead of Firestore
        messages_list.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)
        
        # Count unread messages
        unread_count = len([m for m in messages_list if not m.get('read', False)])
        
        # Mark all as read when viewing
        for message in messages_list:
            if not message.get('read', False):
                try:
                    db.collection('messages').document(message['id']).update({
                        'read': True,
                        'read_at': datetime.now()
                    })
                except Exception as e:
                    print(f"⚠️ Error marking message as read: {e}")
        
        return render_template('contractor/messages.html', 
                             messages=messages_list, 
                             unread_count=unread_count)
        
    except Exception as e:
        print(f'❌ Error loading messages: {str(e)}')
        import traceback
        traceback.print_exc()
        flash(f'Error loading messages: {str(e)}', 'error')
        return redirect(url_for('contractor.dashboard'))