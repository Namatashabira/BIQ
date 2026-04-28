import re
from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware

class CSRFExemptMiddleware(CsrfViewMiddleware):
    def process_view(self, request, callback, callback_args, callback_kwargs):
        if hasattr(settings, 'CSRF_EXEMPT_URLS'):
            for url_pattern in settings.CSRF_EXEMPT_URLS:
                if re.match(url_pattern, request.path_info.lstrip('/')):
                    return None
        return super().process_view(request, callback, callback_args, callback_kwargs)