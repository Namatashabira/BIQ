from rest_framework import serializers
from .models import CustomerReview

class CustomerReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerReview
        fields = [
            'id', 'product_id', 'product_name', 'product_details',
            'rating', 'feedback', 'reviewer_name', 'created_at', 'user_ip'
        ]
        read_only_fields = ['id', 'created_at', 'user_ip']
