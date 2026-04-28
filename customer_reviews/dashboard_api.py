from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import CustomerReview
from .serializers import CustomerReviewSerializer

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_product_reviews(request):
    """
    Returns all product reviews for dashboard display. Optionally filter by product_id.
    """
    product_id = request.query_params.get("product_id")
    qs = CustomerReview.objects.all().order_by("-created_at")
    if product_id:
        qs = qs.filter(product_id=product_id)
    serializer = CustomerReviewSerializer(qs, many=True)
    return Response(serializer.data)
