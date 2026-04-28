from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from business_reports.models import SavedBusinessReport
from .serializers import SavedBusinessReportSerializer

class SavedBusinessReportViewSet(viewsets.ModelViewSet):
    serializer_class = SavedBusinessReportSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SavedBusinessReport.objects.filter(tenant=self.request.user.tenant).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)

    @action(detail=True, methods=['post'])
    def regenerate(self, request, pk=None):
        # Optionally implement regeneration logic
        return Response({'detail': 'Not implemented'}, status=status.HTTP_501_NOT_IMPLEMENTED)
