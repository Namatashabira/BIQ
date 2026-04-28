from rest_framework import serializers
from business_reports.models import SavedBusinessReport

class SavedBusinessReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedBusinessReport
        fields = [
            'id',
            'tenant',
            'created_at',
            'data',
            'name',
            'start_date',
            'end_date',
        ]
        read_only_fields = ['id', 'tenant', 'created_at']
