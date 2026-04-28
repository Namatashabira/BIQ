class NarrativeBuilder:
    """
    Converts metrics into human-readable business language.
    """

    @staticmethod
    def executive_summary(sales, expenses):
        profit = sales["total_sales"] - expenses["total_expenses"]

        return (
            f"During the reporting period, the business generated total sales "
            f"of UGX {sales['total_sales']:,.0f} while incurring total expenses "
            f"of UGX {expenses['total_expenses']:,.0f}. "
            f"This resulted in a net {'profit' if profit >= 0 else 'loss'} "
            f"of UGX {abs(profit):,.0f}."
        )

    @staticmethod
    def sales_section(metrics):
        return (
            f"Total sales amounted to UGX {metrics['total_sales']:,.0f} "
            f"from {metrics['total_orders']} orders, with an average order "
            f"value of UGX {metrics['average_order_value']:,.0f}."
        )

    @staticmethod
    def expense_section(metrics):
        return (
            f"Operational expenses totaled UGX {metrics['total_expenses']:,.0f}. "
            f"Major cost drivers were transport, utilities, and supplies."
        )

    @staticmethod
    def inventory_section(metrics):
        if metrics["low_stock_items"]:
            return (
                f"There are {len(metrics['low_stock_items'])} products currently "
                f"below the recommended stock level, which may impact future sales."
            )
        return "Inventory levels remained healthy throughout the period."
