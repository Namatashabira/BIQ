import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger("django.request")


def custom_exception_handler(exc, context):
    """
    Extends DRF's default handler so that ANY unhandled exception returns
    a structured JSON 500 instead of Django's HTML error page.
    """
    response = exception_handler(exc, context)

    if response is not None:
        return response

    # Unhandled exception — log the full traceback and return JSON
    request = context.get("request")
    view = context.get("view")
    logger.error(
        "Unhandled exception in %s %s (view: %s)",
        getattr(request, "method", "?"),
        getattr(request, "path", "?"),
        view.__class__.__name__ if view else "?",
        exc_info=exc,
    )

    return Response(
        {"error": "An unexpected server error occurred. Please try again."},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
