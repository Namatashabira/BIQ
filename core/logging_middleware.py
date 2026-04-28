import logging
import time
from django.utils.deprecation import MiddlewareMixin
import sys

logger = logging.getLogger('core')

def safe_log(msg, level="info"):
    """
    Safely log a message, replacing characters that can't be printed
    """
    try:
        if level == "info":
            logger.info(msg)
        elif level == "debug":
            logger.debug(msg)
        elif level == "error":
            logger.error(msg)
    except UnicodeEncodeError:
        # Replace non-printable characters
        msg_safe = msg.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)
        if level == "info":
            logger.info(msg_safe)
        elif level == "debug":
            logger.debug(msg_safe)
        elif level == "error":
            logger.error(msg_safe)

class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log all HTTP requests and responses
    """
    
    def process_request(self, request):
        request.start_time = time.time()
        
        # Log request details
        safe_log(f"{request.method} {request.get_full_path()} - IP: {self.get_client_ip(request)}")
        
        # Log request headers (excluding sensitive ones)
        headers = {k: v for k, v in request.META.items() 
                  if k.startswith('HTTP_') and 'AUTH' not in k and 'TOKEN' not in k}
        if headers:
            safe_log(f"Headers: {headers}", level="debug")
            
        # Log request body for POST/PUT/PATCH
        if request.method in ['POST', 'PUT', 'PATCH'] and hasattr(request, 'body'):
            try:
                body = request.body.decode('utf-8')[:500]  # Limit to 500 chars
                if body:
                    safe_log(f"Request body: {body}")
            except:
                safe_log("Could not decode request body", level="debug")
    
    def process_response(self, request, response):
        # Calculate response time
        duration_ms = 0
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            duration_ms = round(duration * 1000, 2)
        
        # Log response
        status_text = self.get_status_text(response.status_code)
        safe_log(f"{status_text} {request.method} {request.get_full_path()} - {response.status_code} - {duration_ms}ms")
        
        # Log response content for errors
        if response.status_code >= 400:
            try:
                content = response.content.decode('utf-8')[:300]
                if content:
                    safe_log(f"Error response: {content}", level="error")
            except:
                safe_log("Could not decode error response", level="error")
        
        return response
    
    def get_client_ip(self, request):
        """Get the client's IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def get_status_text(self, status_code):
        """Get text based on HTTP status code instead of emoji"""
        if 200 <= status_code < 300:
            return "OK"
        elif 300 <= status_code < 400:
            return "REDIRECT"
        elif 400 <= status_code < 500:
            return "CLIENT_ERROR"
        elif status_code >= 500:
            return "SERVER_ERROR"
        else:
            return "UNKNOWN"
