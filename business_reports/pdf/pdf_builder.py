from io import BytesIO
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
from reportlab.lib.units import cm
from datetime import datetime


class BusinessReportPDFBuilder:
    """
    Builds a professional PDF business report from structured report data.
    """

    def __init__(self, report_data, business_name, start_date, end_date):
        self.report = report_data
        self.business_name = business_name
        self.start_date = start_date
        self.end_date = end_date
        self.buffer = BytesIO()
        self.styles = getSampleStyleSheet()

        self._register_styles()

    def _register_styles(self):
        self.styles.add(
            ParagraphStyle(
                name="TitleStyle",
                fontSize=20,
                leading=24,
                alignment=TA_CENTER,
                spaceAfter=20,
                textColor=colors.black,
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="HeaderStyle",
                fontSize=14,
                leading=18,
                spaceBefore=16,
                spaceAfter=8,
                textColor=colors.black,
                fontName="Helvetica-Bold",
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="BodyStyle",
                fontSize=10.5,
                leading=15,
                spaceAfter=10,
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="SmallStyle",
                fontSize=9,
                leading=12,
                textColor=colors.grey,
            )
        )

    def build(self):
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        elements = []

        # -----------------------------
        # COVER PAGE
        # -----------------------------
        elements.append(Paragraph(self.business_name, self.styles["TitleStyle"]))
        elements.append(Spacer(1, 12))

        elements.append(
            Paragraph(
                "Business Performance Report",
                self.styles["HeaderStyle"],
            )
        )

        elements.append(
            Paragraph(
                f"Reporting Period: {self.start_date} to {self.end_date}",
                self.styles["BodyStyle"],
            )
        )

        elements.append(
            Paragraph(
                f"Date Generated: {datetime.now().strftime('%d %B %Y')}",
                self.styles["SmallStyle"],
            )
        )

        elements.append(PageBreak())

        # -----------------------------
        # EXECUTIVE SUMMARY
        # -----------------------------
        elements.append(
            Paragraph("1. Executive Summary", self.styles["HeaderStyle"])
        )
        elements.append(
            Paragraph(
                self.report["executive_summary"],
                self.styles["BodyStyle"],
            )
        )

        # -----------------------------
        # SALES PERFORMANCE
        # -----------------------------
        sales = self.report["sales"]

        elements.append(
            Paragraph("2. Sales Performance", self.styles["HeaderStyle"])
        )
        elements.append(
            Paragraph(sales["narrative"], self.styles["BodyStyle"])
        )

        sales_table = Table(
            [
                ["Metric", "Value"],
                ["Total Sales", f"UGX {sales['metrics']['total_sales']:,.0f}"],
                ["Total Orders", sales["metrics"]["total_orders"]],
                [
                    "Average Order Value",
                    f"UGX {sales['metrics']['average_order_value']:,.0f}",
                ],
            ],
            colWidths=[7 * cm, 7 * cm],
        )

        sales_table.setStyle(self._table_style())
        elements.append(sales_table)

        # -----------------------------
        # EXPENSES
        # -----------------------------
        expenses = self.report["expenses"]

        elements.append(
            Paragraph("3. Expense Analysis", self.styles["HeaderStyle"])
        )
        elements.append(
            Paragraph(expenses["narrative"], self.styles["BodyStyle"])
        )

        expense_rows = [["Category", "Amount (UGX)"]]
        for row in expenses["metrics"]["breakdown"]:
            expense_rows.append(
                [
                    row["category__name"],
                    f"{row['total']:,.0f}",
                ]
            )

        expense_table = Table(expense_rows, colWidths=[7 * cm, 7 * cm])
        expense_table.setStyle(self._table_style())
        elements.append(expense_table)

        # -----------------------------
        # TAX SUMMARY
        # -----------------------------
        taxes = self.report["taxes"]

        elements.append(
            Paragraph("4. Tax Summary", self.styles["HeaderStyle"])
        )
        elements.append(
            Paragraph(
                f"VAT collected during the period amounted to "
                f"UGX {taxes['vat_collected']:,.0f}.",
                self.styles["BodyStyle"],
            )
        )

        # -----------------------------
        # INVENTORY
        # -----------------------------
        inventory = self.report["inventory"]

        elements.append(
            Paragraph("5. Inventory & Stock Status", self.styles["HeaderStyle"])
        )
        elements.append(
            Paragraph(inventory["narrative"], self.styles["BodyStyle"])
        )

        if inventory["metrics"]["low_stock_items"]:
            stock_rows = [["Product", "Quantity"]]
            for item in inventory["metrics"]["low_stock_items"]:
                stock_rows.append([item["name"], item["quantity"]])

            stock_table = Table(stock_rows, colWidths=[7 * cm, 7 * cm])
            stock_table.setStyle(self._table_style())
            elements.append(stock_table)

        # -----------------------------
        # CONCLUSION
        # -----------------------------
        elements.append(
            Paragraph("6. Conclusion", self.styles["HeaderStyle"])
        )
        elements.append(
            Paragraph(
                "This report provides a comprehensive overview of the business "
                "performance during the reporting period. Continued monitoring of "
                "sales growth, expense control, and inventory levels will support "
                "sustained profitability.",
                self.styles["BodyStyle"],
            )
        )

        doc.build(elements)
        self.buffer.seek(0)
        return self.buffer

    @staticmethod
    def _table_style():
        return TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ]
        )
