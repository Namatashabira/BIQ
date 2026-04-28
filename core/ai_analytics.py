# AI-Powered Analytics & Insights Module (Tenant-Aware)
import numpy as np
from datetime import datetime, timedelta


class AIAnalytics:
    """
    AI-powered analytics engine for sales forecasting, inventory optimization,
    customer behavior analysis, and profit/loss predictions.
    Tenant-aware: No tenant sees another tenant's data.
    """

    # --------------------------
    # Sales Forecast
    # --------------------------
    @staticmethod
    def sales_forecast(orders_data, tenant_id=None, days_ahead=30):
        """
        Forecast sales for the next N days using linear trend analysis
        """
        try:
            # Filter orders by tenant
            if tenant_id:
                orders_data = [o for o in orders_data if o.get('tenant_id') == tenant_id]

            if not orders_data or len(orders_data) < 3:
                return {
                    'forecast': [],
                    'confidence': 'low',
                    'trend': 'insufficient_data',
                    'message': 'Not enough historical data for accurate forecasting'
                }

            dates = [item['date'] for item in orders_data]
            sales = [float(item['total']) for item in orders_data]

            n = len(sales)
            x = np.arange(n)
            y = np.array(sales)
            slope = (n * np.sum(x * y) - np.sum(x) * np.sum(y)) / (n * np.sum(x**2) - np.sum(x)**2)
            intercept = (np.sum(y) - slope * np.sum(x)) / n

            forecast_data = []
            last_date = datetime.fromisoformat(dates[-1].replace('Z', '+00:00'))

            for i in range(days_ahead):
                future_x = n + i
                predicted_value = max(0, slope * future_x + intercept)
                future_date = last_date + timedelta(days=i + 1)
                forecast_data.append({
                    'date': future_date.strftime('%Y-%m-%d'),
                    'predicted_sales': round(predicted_value, 2),
                    'confidence': 'high' if i < 7 else 'medium' if i < 14 else 'low'
                })

            trend = 'increasing' if slope > 0 else 'decreasing' if slope < 0 else 'stable'
            avg_sales = np.mean(sales)
            std_dev = np.std(sales)

            return {
                'forecast': forecast_data,
                'trend': trend,
                'slope': round(float(slope), 2),
                'average_daily_sales': round(float(avg_sales), 2),
                'variability': round(float(std_dev), 2),
                'confidence': 'high' if std_dev < avg_sales * 0.3 else 'medium',
                'insights': AIAnalytics._generate_sales_insights(trend, slope, avg_sales)
            }

        except Exception as e:
            return {'error': str(e), 'forecast': [], 'confidence': 'low'}

    @staticmethod
    def _generate_sales_insights(trend, slope, avg_sales):
        insights = []
        if trend == 'increasing':
            insights.append(f"[trending-up] Sales are trending upward with an average increase of ${abs(slope):.2f}/day")
            insights.append("[check-circle] Consider increasing inventory to meet growing demand")
        elif trend == 'decreasing':
            insights.append(f"[trending-down] Sales are declining by approximately ${abs(slope):.2f}/day")
            insights.append("[alert-triangle] Review marketing strategies and customer feedback")
        else:
            insights.append("[arrow-right] Sales are stable with minimal fluctuation")
            insights.append("[lightbulb] Good time to experiment with promotions")
        insights.append(f"[dollar-sign] Average daily sales: ${avg_sales:.2f}")
        return insights

    # --------------------------
    # Inventory Optimization
    # --------------------------
    @staticmethod
    def inventory_optimization(products_data, orders_data, tenant_id=None):
        """
        Analyze inventory and provide optimization suggestions, tenant-aware
        """
        try:
            if tenant_id:
                products_data = [p for p in products_data if p.get('tenant_id') == tenant_id]
                orders_data = [o for o in orders_data if o.get('tenant_id') == tenant_id]

            critical_items, suggestions, overstock_items, optimal_items = [], [], [], []

            for product in products_data:
                name = product.get('name', 'Unknown')
                current_stock = product.get('stock', 0)

                product_orders = [
                    order for order in orders_data
                    if any(item.get('product_name') == name for item in order.get('items', []))
                ]

                total_sold = sum(
                    sum(item.get('quantity', 0) for item in order.get('items', []) if item.get('product_name') == name)
                    for order in product_orders
                )

                days_range = 30
                daily_velocity = total_sold / days_range if days_range > 0 else 0
                days_until_stockout = current_stock / daily_velocity if daily_velocity > 0 else float('inf')
                recommended_stock = daily_velocity * 30

                status = {
                    'product_name': name,
                    'current_stock': current_stock,
                    'daily_velocity': round(daily_velocity, 2),
                    'days_until_stockout': round(days_until_stockout, 1) if days_until_stockout != float('inf') else 999,
                    'recommended_stock': round(recommended_stock),
                    'reorder_quantity': max(0, round(recommended_stock - current_stock))
                }

                if days_until_stockout < 7:
                    status.update({'priority': 'critical', 'action': f"[alert-triangle] URGENT: Only {days_until_stockout:.1f} days of stock remaining"})
                    critical_items.append(status)
                elif days_until_stockout < 14:
                    status.update({'priority': 'high', 'action': f"[bell] Reorder soon. {days_until_stockout:.1f} days remaining"})
                    suggestions.append(status)
                elif current_stock > recommended_stock * 2:
                    status.update({'priority': 'overstock', 'action': "[package] Overstocked. Consider promotions"})
                    overstock_items.append(status)
                else:
                    status.update({'priority': 'optimal', 'action': "[check-circle] Stock level is optimal"})
                    optimal_items.append(status)

            return {
                'critical_items': critical_items,
                'reorder_soon': suggestions,
                'overstocked': overstock_items,
                'optimal': optimal_items,
                'summary': {
                    'total_products': len(products_data),
                    'critical_count': len(critical_items),
                    'reorder_count': len(suggestions),
                    'overstock_count': len(overstock_items),
                    'optimal_count': len(optimal_items)
                }
            }

        except Exception as e:
            return {'error': str(e), 'critical_items': [], 'reorder_soon': [], 'overstocked': [], 'optimal': []}

    # --------------------------
    # Customer Behavior
    # --------------------------
    @staticmethod
    def customer_behavior_analysis(orders_data, tenant_id=None):
        """
        Analyze customer behavior, tenant-aware
        """
        try:
            if tenant_id:
                orders_data = [o for o in orders_data if o.get('tenant_id') == tenant_id]

            if not orders_data:
                return {'insights': ['No order data'], 'segments': [], 'recommendations': []}

            customer_metrics = {}
            for order in orders_data:
                customer_id = order.get('customer_id') or order.get('customer_name', 'Guest')
                total = float(order.get('total', 0))
                metrics = customer_metrics.setdefault(customer_id, {'total_spent': 0, 'order_count': 0, 'orders': []})
                metrics['total_spent'] += total
                metrics['order_count'] += 1
                metrics['orders'].append(order)

            total_revenue = sum(m['total_spent'] for m in customer_metrics.values())
            total_orders = sum(m['order_count'] for m in customer_metrics.values())
            avg_order_value = total_revenue / total_orders if total_orders > 0 else 0

            high_value, medium_value, low_value = [], [], []
            for customer_id, metrics in customer_metrics.items():
                avg_customer_value = metrics['total_spent'] / metrics['order_count']
                segment = {
                    'customer_id': customer_id,
                    'total_spent': round(metrics['total_spent'], 2),
                    'order_count': metrics['order_count'],
                    'avg_order_value': round(avg_customer_value, 2)
                }
                if avg_customer_value > avg_order_value * 1.5:
                    high_value.append(segment)
                elif avg_customer_value > avg_order_value * 0.8:
                    medium_value.append(segment)
                else:
                    low_value.append(segment)

            insights = [
                f"[bar-chart] Total customers: {len(customer_metrics)}",
                f"[dollar-sign] Average order value: ${avg_order_value:.2f}",
                f"[star] High-value customers: {len(high_value)} ({len(high_value)/len(customer_metrics)*100:.1f}%)",
                f"[users] Total orders: {total_orders}",
                f"[trending-up] Avg orders per customer: {total_orders/len(customer_metrics):.1f}"
            ]

            recommendations = []
            if high_value:
                recommendations.append("[target] Retain high-value customers with loyalty programs")
            if len(low_value)/len(customer_metrics) > 0.5:
                recommendations.append("[lightbulb] Target campaigns to increase low-value orders")
            if avg_order_value < 50:
                recommendations.append("[package] Consider bundle deals")

            return {
                'insights': insights,
                'segments': {
                    'high_value': sorted(high_value, key=lambda x: x['total_spent'], reverse=True)[:10],
                    'medium_value': len(medium_value),
                    'low_value': len(low_value)
                },
                'recommendations': recommendations,
                'metrics': {
                    'total_customers': len(customer_metrics),
                    'total_revenue': round(total_revenue, 2),
                    'avg_order_value': round(avg_order_value, 2),
                    'total_orders': total_orders
                }
            }

        except Exception as e:
            return {'error': str(e), 'insights': [], 'segments': {}, 'recommendations': []}

    # --------------------------
    # Profit/Loss Prediction
    # --------------------------
    @staticmethod
    def profit_loss_prediction(financial_data, tenant_id=None):
        """
        Predict future profit/loss, tenant-aware
        """
        try:
            if tenant_id:
                financial_data = [f for f in financial_data if f.get('tenant_id') == tenant_id]

            if not financial_data:
                return {'prediction': 'insufficient_data', 'insights': ['Not enough data for prediction']}

            revenues = [float(r.get('revenue', 0)) for r in financial_data]
            expenses = [float(r.get('expense', 0)) for r in financial_data]
            profits = [rev - exp for rev, exp in zip(revenues, expenses)]

            avg_profit = np.mean(profits)
            avg_revenue = np.mean(revenues)
            avg_expense = np.mean(expenses)
            profit_margin = (avg_profit / avg_revenue * 100) if avg_revenue > 0 else 0

            n = len(profits)
            x = np.arange(n)
            revenue_slope = np.polyfit(x, revenues, 1)[0] if n > 1 else 0
            expense_slope = np.polyfit(x, expenses, 1)[0] if n > 1 else 0

            revenue_prediction = revenues[-1] + revenue_slope
            expense_prediction = expenses[-1] + expense_slope
            profit_prediction = revenue_prediction - expense_prediction

            insights = []
            if profit_prediction > avg_profit * 1.1:
                insights.append("[trending-up] Profit predicted to increase")
                insights.append(f"[check-circle] Expected profit: ${profit_prediction:.2f}")
            elif profit_prediction < avg_profit * 0.9:
                insights.append("[trending-down] Profit predicted to decrease")
                insights.append(f"[alert-triangle] Expected profit: ${profit_prediction:.2f}")
            else:
                insights.append("[arrow-right] Profit expected to remain stable")
                insights.append(f"[dollar-sign] Expected profit: ${profit_prediction:.2f}")

            insights.append(f"[bar-chart] Current profit margin: {profit_margin:.1f}%")
            if profit_margin < 15:
                insights.append("[alert-triangle] Low profit margin")
            elif profit_margin > 30:
                insights.append("[check-circle] Healthy profit margin")

            return {
                'prediction': {
                    'next_month_profit': round(profit_prediction, 2),
                    'next_month_revenue': round(revenue_prediction, 2),
                    'next_month_expense': round(expense_prediction, 2),
                    'profit_margin': round(profit_margin, 2)
                },
                'trends': {
                    'revenue_trend': 'increasing' if revenue_slope > 0 else 'decreasing',
                    'expense_trend': 'increasing' if expense_slope > 0 else 'decreasing',
                    'profit_trend': 'increasing' if profit_prediction > avg_profit else 'decreasing'
                },
                'insights': insights,
                'historical': {
                    'avg_profit': round(avg_profit, 2),
                    'avg_revenue': round(avg_revenue, 2),
                    'avg_expense': round(avg_expense, 2)
                }
            }

        except Exception as e:
            return {'error': str(e), 'prediction': None, 'insights': []}
