from django.utils.deprecation import MiddlewareMixin

class TenantMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.tenant = None
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            request.tenant = getattr(user, "tenant", None)
