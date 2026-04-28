from django.http import JsonResponse
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET

from business_reports.services.report_builder import BusinessReportBuilder


@require_GET
def generate_business_report(request):
    tenant = request.user.tenant  # adjust if your tenant access differs

    start_date = parse_date(request.GET.get("start"))
    end_date = parse_date(request.GET.get("end"))

    report = BusinessReportBuilder.build(
        start_date=start_date,
        end_date=end_date,
        tenant=tenant
    )

    return JsonResponse(report, safe=False)
