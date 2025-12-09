from flask_login import UserMixin
from datetime import datetime

class User(UserMixin):
    """User model for all roles (user, admin, contractor, supplier)"""
    
    def __init__(self, user_id, user_data):
        self.id = user_id
        self.name = user_data.get('name', '')
        self.email = user_data.get('email', '')
        self.phone = user_data.get('phone', '')
        self.role = user_data.get('role', 'user')  # user, admin, contractor, supplier
        self.created_at = user_data.get('created_at', datetime.now())
        self.verified = user_data.get('verified', False)
        self.active = user_data.get('active', True)
        
        # Role-specific fields
        if self.role == 'contractor':
            self.company_name = user_data.get('company_name', '')
            self.experience = user_data.get('experience', 0)
            self.rating = user_data.get('rating', 0.0)
            self.completed_projects = user_data.get('completed_projects', 0)
            self.license_number = user_data.get('license_number', '')
            
        elif self.role == 'supplier':
            self.company_name = user_data.get('company_name', '')
            self.business_type = user_data.get('business_type', '')
            self.rating = user_data.get('rating', 0.0)
            self.gst_number = user_data.get('gst_number', '')
            
        elif self.role == 'admin':
            self.permissions = user_data.get('permissions', [])
    
    def get_id(self):
        """Return user ID for Flask-Login"""
        return self.id
    
    def is_active(self):
        """Check if user is active"""
        return self.active
    
    def is_verified(self):
        """Check if user is verified"""
        return self.verified
    
    def to_dict(self):
        """Convert user object to dictionary"""
        user_dict = {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'role': self.role,
            'created_at': self.created_at,
            'verified': self.verified,
            'active': self.active
        }
        
        # Add role-specific fields
        if self.role == 'contractor':
            user_dict.update({
                'company_name': self.company_name,
                'experience': self.experience,
                'rating': self.rating,
                'completed_projects': self.completed_projects,
                'license_number': self.license_number
            })
        elif self.role == 'supplier':
            user_dict.update({
                'company_name': self.company_name,
                'business_type': self.business_type,
                'rating': self.rating,
                'gst_number': self.gst_number
            })
        elif self.role == 'admin':
            user_dict.update({
                'permissions': self.permissions
            })
            
        return user_dict