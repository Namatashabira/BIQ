"""
Middleware to automatically track and log all accounting module access and changes
"""
from django.utils.deprecation import MiddlewareMixin
from .models import AuditLog
import json


class AccountingAuditMiddleware(MiddlewareMixin):
    """
    Automatically logs all accounting-related actions for security and compliance
    """
    
    TRACKED_PATHS = [
        '/api/accounting/expenses',
        '/api/accounting/payments',
        '/api/accounting/taxes',
        '/api/accounting/assets',
        '/api/accounting/liabilities',
        '/api/accounting/equity',
    ]
    
    MODEL_MAP = {
        'expenses': 'expense',
        'payments': 'payment',
        'taxes': 'tax',
        'assets': 'asset',
        'liabilities': 'liability',
        'equity': 'equity',
    }
    
    ACTION_MAP = {
        'GET': 'view',
        'POST': 'create',
        'PUT': 'update',
        'PATCH': 'update',
        'DELETE': 'delete',
    }
    
    def process_response(self, request, response):
        """Log accounting actions after successful requests"""
        
        # Only track authenticated users
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return response
        
        # Check if this is an accounting endpoint
        path = request.path
        is_accounting_request = any(tracked in path for tracked in self.TRACKED_PATHS)
        
        if not is_accounting_request:
            return response
        
        # Only log successful requests (200-299 status codes)
        if not (200 <= response.status_code < 300):
            return response
        
        try:
            # Determine model type from path
            model_type = None
            for key, value in self.MODEL_MAP.items():
                if key in path:
                    model_type = value
                    break
            
            if not model_type:
                return response
            
            # Determine action
            action = self.ACTION_MAP.get(request.method, 'view')
            
            # Get tenant
            tenant = getattr(request.user, 'tenant', None)
            if not tenant:
                return response
            
            # Extract object ID from path or response
            object_id = None
            object_repr = f"{model_type} operation"
            
            # Try to get ID from URL path (e.g., /api/accounting/expenses/123/)
            path_parts = [p for p in path.split('/') if p.isdigit()]
            if path_parts:
                object_id = int(path_parts[0])
            
            # For list views (GET without ID), log the summary access
            if action == 'view' and not object_id:
                if 'summary' in path:
                    object_repr = f"{model_type} summary accessed"
                else:
                    object_repr = f"{model_type} list accessed"
                object_id = 0  # Use 0 for list/summary views
            
            # Try to parse response for created/updated object info
            if hasattr(response, 'data') and isinstance(response.data, dict):
                if 'id' in response.data:
                    object_id = response.data['id']
                    if 'party_name' in response.data:
                        object_repr = f"Payment: {response.data['party_name']}"
                    elif 'vendor' in response.data:
                        object_repr = f"Expense: {response.data['vendor']}"
                    elif 'tax_type' in response.data:
                        object_repr = f"Tax: {response.data['tax_type']}"
            
            # Get IP address
            ip_address = self.get_client_ip(request)
            
            # Get user agent
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
            
            # Check for suspicious activity
            is_suspicious = self.detect_suspicious_activity(request, action)
            
            # Create audit log
            if object_id is not None:
                AuditLog.objects.create(
                    tenant=tenant,
                    user=request.user,
                    action=action,
                    model_type=model_type,
                    object_id=object_id,
                    object_repr=object_repr,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    endpoint=path,
                    method=request.method,
                    is_suspicious=is_suspicious,
                )
        
        except Exception as e:
            # Don't fail the request if logging fails
            print(f"Audit logging error: {str(e)}")
        
        return response
    
    def get_client_ip(self, request):
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def detect_suspicious_activity(self, request, action):
        """Detect potentially suspicious patterns"""
        # Check for rapid-fire requests (would need session/cache)
        # Check for unusual times (would need timezone)
        # Check for bulk deletions
        # For now, just flag bulk operations
        
        if action == 'delete':
            return True  # Flag all deletions for review
        
        return False
