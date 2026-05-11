from rest_framework import serializers
from .models import AIReportComment


class AIReportCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIReportComment
        fields = [
            'id', 'report_snapshot_id', 'student', 'term', 'academic_year',
            'comment', 'overall_score', 'generated_by_ai',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
