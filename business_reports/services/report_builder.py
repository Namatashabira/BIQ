from .metrics import ReportMetricsService
from .narrative import NarrativeBuilder


class BusinessReportBuilder:
    """
    Builds a full structured business report.
    """

    @staticmethod
    def build(start_date, end_date, tenant):
        sales = ReportMetricsService.sales_metrics(start_date, end_date, tenant)
        expenses = ReportMetricsService.expense_metrics(start_date, end_date, tenant)
        orders = ReportMetricsService.order_metrics(start_date, end_date, tenant)
        inventory = ReportMetricsService.inventory_metrics(tenant)
        taxes = ReportMetricsService.tax_metrics(start_date, end_date, tenant)

        return {
            "executive_summary": NarrativeBuilder.executive_summary(sales, expenses),
            "sales": {
                "metrics": sales,
                "narrative": NarrativeBuilder.sales_section(sales),
            },
            "expenses": {
                "metrics": expenses,
                "narrative": NarrativeBuilder.expense_section(expenses),
            },
            "inventory": {
                "metrics": inventory,
                "narrative": NarrativeBuilder.inventory_section(inventory),
            },
            "taxes": taxes,
            "orders": orders,
        }
