from datetime import date, timedelta, datetime
import logging

from django.db.models import Sum, Count
from django.contrib.auth import get_user_model

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from product.models import Product
from core.orders.models import Order, OrderItem
from tenants.models import TenantMembership
from core.auth_views import ensure_tenant_for_user

User = get_user_model()
logger = logging.getLogger(__name__)


# ======================================================
# Helpers
# ======================================================
def get_user_tenant(user):
    tenant = None
    if hasattr(user, "tenant") and user.tenant:
        tenant = user.tenant
    else:
        membership = TenantMembership.objects.filter(user=user).first()
        if membership:
            tenant = membership.tenant

    # Auto-create/verify tenant so authenticated users can access dashboard
    if not tenant:
        tenant = ensure_tenant_for_user(user)
    elif not getattr(tenant, 'is_verified', False):
        tenant.is_verified = True
        tenant.save(update_fields=["is_verified"])

    return tenant


def get_user_role(user, tenant):
    membership = TenantMembership.objects.filter(
        user=user, tenant=tenant
    ).first()
    return membership.role if membership else "staff"


# ======================================================
# DASHBOARD STATS
# ======================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    user = request.user
    try:
        tenant = get_user_tenant(user)
    except PermissionError as exc:
        return Response({"detail": str(exc)}, status=403)
    except Exception as exc:
        logger.exception("dashboard_stats tenant resolution failed")
        return Response({"detail": "Unable to resolve tenant"}, status=500)

    if not tenant:
        return Response(
            {"detail": "User is not associated with any tenant"},
            status=403,
        )

    user_role = get_user_role(user, tenant)

    today = date.today()
    expiring_soon_date = today + timedelta(days=30)
    last_30_days = today - timedelta(days=30)
    last_7_days = today - timedelta(days=7)

    # ==================================================
    # TENANT-SCOPED QUERYSETS
    # ==================================================
    products = Product.objects.filter(tenant=tenant)
    orders = Order.objects.filter(tenant=tenant)
    users = User.objects.filter(
        tenant_memberships__tenant=tenant
    ).distinct()

    # ==================================================
    # Auto-update product statuses (tenant only)
    # ==================================================
    for product in products:
        if product.auto_update_status():
            product.save(update_fields=["status", "updated_at"])

    # ==================================================
    # PRODUCT METRICS
    # ==================================================
    total_products = products.count()
    total_stock = products.aggregate(total=Sum("stock"))["total"] or 0

    active_products = products.filter(status="active").count()
    inactive_products = products.filter(status="inactive").count()

    out_of_stock = products.filter(stock=0).count()
    low_stock = products.filter(stock__gt=0, stock__lte=10).count()
    in_stock = products.filter(stock__gt=10).count()

    expired_products = products.filter(
        expiry_date__isnull=False,
        expiry_date__lte=today,
    )
    expired_count = expired_products.count()

    expiring_soon = products.filter(
        expiry_date__isnull=False,
        expiry_date__gte=today,
        expiry_date__lte=expiring_soon_date,
    )
    expiring_soon_count = expiring_soon.count()

    # ==================================================
    # STOCK VALUE
    # ==================================================
    total_stock_value = 0
    current_stock_value = 0
    expired_stock_value = 0

    for product in products:
        value = float(product.retail_price or 0) * product.stock
        total_stock_value += value

        if product.status == "active" and product.stock > 0:
            current_stock_value += value

        if product.is_expired():
            expired_stock_value += value

    # ==================================================
    # ORDERS & REVENUE
    # ==================================================
    total_orders = orders.count()
    completed_orders = orders.filter(
        status__in=["confirmed", "delivered"]
    ).count()
    pending_orders = orders.filter(status="pending").count()
    failed_orders = orders.filter(status="cancelled").count()

    order_status_breakdown = [
        {"status": "pending", "count": pending_orders},
        {"status": "confirmed", "count": orders.filter(status="confirmed").count()},
        {"status": "delivered", "count": orders.filter(status="delivered").count()},
        {"status": "cancelled", "count": failed_orders},
    ]

    total_revenue = orders.filter(
        status__in=["confirmed", "delivered"]
    ).aggregate(total=Sum("total"))["total"] or 0

    revenue_last_30_days = orders.filter(
        status__in=["confirmed", "delivered"],
        date__gte=last_30_days,
    ).aggregate(total=Sum("total"))["total"] or 0

    revenue_last_7_days = orders.filter(
        status__in=["confirmed", "delivered"],
        date__gte=last_7_days,
    ).aggregate(total=Sum("total"))["total"] or 0

    # ==================================================
    # SALES TREND (30 DAYS)
    # ==================================================
    sales_trend = []
    for i in range(30):
        day = today - timedelta(days=29 - i)
        day_orders = orders.filter(date__date=day)

        sales_trend.append({
            "date": day.isoformat(),
            "orders": day_orders.count(),
            "revenue": float(
                day_orders.filter(
                    status__in=["confirmed", "delivered"]
                ).aggregate(total=Sum("total"))["total"] or 0
            ),
        })

    # ==================================================
    # RECENT ACTIVITY
    # ==================================================
    recent_products = products.order_by("-updated_at")[:5]
    stock_updates = [
        {
            "id": p.id,
            "name": p.name,
            "stock": p.stock,
            "status": p.status,
            "updated_at": p.updated_at.isoformat(),
        }
        for p in recent_products
    ]

    latest_orders = orders.order_by("-date")[:10]
    latest_orders_data = [
        {
            "id": o.id,
            "order_number": f"ORD-{o.id}",
            "total": float(o.total),
            "status": o.status,
            "created_at": o.date.isoformat(),
            "items_count": o.items.count(),
        }
        for o in latest_orders
    ]

    # ==================================================
    # RESPONSE
    # ==================================================
    response_data = {
        "kpi_cards": {
            "revenue": {
                "total": float(total_revenue),
                "last_30_days": float(revenue_last_30_days),
                "last_7_days": float(revenue_last_7_days),
            },
            "orders": {
                "total": total_orders,
                "completed": completed_orders,
                "pending": pending_orders,
                "failed": failed_orders,
            },
            "stock": {
                "total_products": total_products,
                "total_stock": total_stock,
                "active": active_products,
                "inactive": inactive_products,
                "low_stock": low_stock,
                "out_of_stock": out_of_stock,
            },
        },
        "charts": {
            "sales_trend": sales_trend,
            "order_status_breakdown": order_status_breakdown,
        },
        "recent_activity": {
            "latest_orders": latest_orders_data,
            "stock_updates": stock_updates,
        },
        "summary": {
            "stock_value": {
                "total": round(total_stock_value, 2),
                "current": round(current_stock_value, 2),
                "expired": round(expired_stock_value, 2),
            }
        },
        "user_role": user_role,
        "tenant": {
            "id": tenant.id,
            "name": tenant.name,
        },
        "critical_alerts": {
            "delayed_orders": [],
        },
        "last_updated": datetime.now().isoformat(),
    }

    # ==================================================
    # ROLE-BASED VISIBILITY
    # ==================================================
    if user_role == "staff":
        response_data["kpi_cards"]["revenue"] = "restricted"
        response_data["summary"]["stock_value"] = "restricted"

    return Response(response_data)


# ======================================================
# STOCK HISTORY
# ======================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def stock_history(request):
    user = request.user
    tenant = get_user_tenant(user)

    if not tenant:
        return Response({"detail": "No tenant"}, status=403)

    thirty_days_ago = date.today() - timedelta(days=30)

    orders = Order.objects.filter(
        tenant=tenant,
        date__gte=thirty_days_ago,
        status__in=["confirmed", "delivered"],
    ).prefetch_related("items__product")

    movements = []
    for order in orders:
        for item in order.items.all():
            movements.append({
                "date": order.date.isoformat(),
                "product_id": item.product.id,
                "product_name": item.product.name,
                "quantity": item.quantity,
                "type": "sale",
                "order_number": f"ORD-{order.id}",
                "current_stock": item.product.stock,
            })

    return Response({
        "movements": movements,
        "total_movements": len(movements),
    })
