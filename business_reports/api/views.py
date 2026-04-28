from django.http import HttpResponse
from django.utils.timezone import now
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils.dateparse import parse_date

from business_reports.services.report_builder import BusinessReportBuilder
from business_reports.models import SavedBusinessReport
from tenants.models import Tenant, TenantMembership

try:
    from business_reports.pdf.pdf_builder import BusinessReportPDFBuilder
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


def _resolve_tenant(request):
    user = request.user
    tenant = getattr(user, 'tenant', None)
    if not tenant:
        membership = TenantMembership.objects.filter(user=user).first()
        tenant = membership.tenant if membership else None
    return tenant


def _get_date_range(request):
    start = parse_date(request.GET.get('start') or '')
    end = parse_date(request.GET.get('end') or '')
    if not start or not end:
        today = now().date()
        start = today.replace(day=1)
        end = today
    return start, end


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generate_business_report_json(request):
    tenant = _resolve_tenant(request)
    if not tenant:
        return Response({'error': 'No tenant associated with this account.'}, status=403)

    start_date, end_date = _get_date_range(request)

    report = BusinessReportBuilder.build(
        start_date=start_date,
        end_date=end_date,
        tenant=tenant,
    )

    SavedBusinessReport.objects.create(
        tenant=tenant,
        data=report,
        start_date=start_date,
        end_date=end_date,
        name=f"Report {start_date} to {end_date}",
    )

    return Response({
        'business': tenant.name,
        'start_date': str(start_date),
        'end_date': str(end_date),
        'generated_at': str(now()),
        'report': report,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generate_business_report_pdf(request):
    if not PDF_AVAILABLE:
        return Response({'error': 'PDF generation requires reportlab. Run: pip install reportlab'}, status=501)

    tenant = _resolve_tenant(request)
    if not tenant:
        return Response({'error': 'No tenant associated with this account.'}, status=403)

    start_date, end_date = _get_date_range(request)

    report = BusinessReportBuilder.build(
        start_date=start_date,
        end_date=end_date,
        tenant=tenant,
    )

    pdf_buffer = BusinessReportPDFBuilder(
        report_data=report,
        business_name=tenant.name,
        start_date=start_date,
        end_date=end_date,
    ).build()

    filename = f"business_report_{start_date}_{end_date}.pdf"
    response = HttpResponse(pdf_buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
