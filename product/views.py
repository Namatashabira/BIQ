from datetime import date, datetime
import math
import random

from django.db import transaction, IntegrityError
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action

from .models import Product
from .serializers import ProductSerializer


class ProductViewSet(viewsets.ModelViewSet):
    """
    Multi-tenant Product ViewSet
    - Each tenant only sees their own products
    - Status auto-updates safely
    - Real-time UI updates via WebSockets
    """

    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    # ==================================================
    # Tenant resolution
    # ==================================================
    def _get_user_tenant(self, user, request=None):
        """
        Resolve tenant from:
        1. Direct tenant (tenant owner/admin)
        2. Tenant membership (staff/users)
        3. tenant_uuid in request (for API calls)
        """
        from tenants.models import Tenant
        # Priority: tenant_uuid in request data or query params
        tenant_uuid = None
        if request is not None:
            tenant_uuid = request.data.get("tenant_uuid") or request.query_params.get("tenant_uuid")
        if tenant_uuid:
            try:
                tenant = Tenant.objects.get(uuid=tenant_uuid)
                if not tenant.is_verified:
                    raise PermissionError("Tenant account is not verified. Please contact support.")
                return tenant
            except Tenant.DoesNotExist:
                return None
        # Fallback to user association
        if hasattr(user, "tenant") and user.tenant:
            tenant = user.tenant
        else:
            memberships = getattr(user, "tenant_memberships", None)
            if memberships and memberships.exists():
                tenant = memberships.first().tenant
            else:
                tenant = None
        if tenant and not getattr(tenant, 'is_verified', False):
            raise PermissionError("Tenant account is not verified. Please contact support.")
        return tenant

    # ==================================================
    # Queryset (STRICT TENANT FILTER)
    # ==================================================
    def get_queryset(self):
        # Public user view: return active products filtered by tenant_uuid if provided
        if self.request.query_params.get("user_view") == "true":
            tenant_uuid = self.request.query_params.get("tenant_uuid")
            qs = Product.objects.filter(status=Product.STATUS_ACTIVE)
            if tenant_uuid:
                qs = qs.filter(tenant__uuid=tenant_uuid)
            elif self.request.user and self.request.user.is_authenticated:
                tenant = self._get_user_tenant(self.request.user, self.request)
                if tenant:
                    qs = qs.filter(tenant=tenant)
            return qs

        tenant = self._get_user_tenant(self.request.user, self.request)

        if not tenant:
            return Product.objects.none()

        return Product.objects.filter(tenant=tenant)

    def get_permissions(self):
        # Allow anonymous access for public product consumption endpoints
        if self.request.query_params.get("user_view") == "true" and self.action in ["list", "retrieve"]:
            return [AllowAny()]
        if self.action in ["also_buy"]:
            return [AllowAny()]
        return [permission() for permission in self.permission_classes]

    # ==================================================
    # CREATE
    # ==================================================
    def perform_create(self, serializer):
        tenant = self._get_user_tenant(self.request.user, self.request)
        if not tenant:
            raise PermissionError("User is not associated with any tenant")
        serializer.save(tenant=tenant)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                self.perform_create(serializer)
        except IntegrityError as exc:
            if "unique_product_name_per_tenant" in str(exc):
                return Response(
                    {"error": "A product with this name already exists for your tenant."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {"error": "Unable to create product.", "details": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        self._broadcast(
            tenant_uuid=str(serializer.instance.tenant.uuid),
            action="created",
            payload=serializer.data,
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # ==================================================
    # LIST
    # ==================================================
    def list(self, request, *args, **kwargs):
        """
        - Auto-update product statuses
        - Optional user_view=true → only active products
        """
        queryset = self.get_queryset()

        # Auto-update status safely
        for product in queryset:
            if product.auto_update_status():
                product.save(update_fields=["status", "updated_at"])

        if request.query_params.get("user_view") == "true":
            queryset = queryset.filter(status=Product.STATUS_ACTIVE)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    # ==================================================
    # RETRIEVE
    # ==================================================
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance.auto_update_status():
            instance.save(update_fields=["status", "updated_at"])

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    # ==================================================
    # UPDATE
    # ==================================================
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        # -----------------------------
        # Validate expiry date
        # -----------------------------
        expiry_date_str = request.data.get("expiry_date")
        if expiry_date_str:
            try:
                expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d").date()
                if expiry_date < date.today():
                    return Response(
                        {"error": "Expiry date cannot be in the past"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except ValueError:
                pass

        # -----------------------------
        # Manual status control
        # -----------------------------
        manually_inactivated = request.data.get("manually_inactivated")
        status_val = request.data.get("status")

        if manually_inactivated is not None:
            manually_inactivated = str(manually_inactivated).lower() in ("true", "1", "yes")
            instance.manually_inactivated = manually_inactivated

            if manually_inactivated:
                instance.status = Product.STATUS_INACTIVE
            else:
                if not instance.should_be_inactive():
                    instance.status = Product.STATUS_ACTIVE

        elif status_val is not None:
            if status_val == Product.STATUS_INACTIVE:
                instance.manually_inactivated = True
                instance.status = Product.STATUS_INACTIVE
            elif status_val == Product.STATUS_ACTIVE:
                instance.manually_inactivated = False
                if not instance.should_be_inactive():
                    instance.status = Product.STATUS_ACTIVE

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                serializer.save()

                # Final safety auto-update
                if instance.auto_update_status():
                    instance.save(update_fields=["status", "updated_at"])
        except IntegrityError as exc:
            if "unique_product_name_per_tenant" in str(exc):
                return Response(
                    {"error": "A product with this name already exists for your tenant."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {"error": "Unable to update product.", "details": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        self._broadcast(
            tenant_uuid=str(instance.tenant.uuid),
            action="updated",
            payload=serializer.data,
        )

        return Response(serializer.data)

    # ==================================================
    # DELETE
    # ==================================================
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        tenant_uuid = str(instance.tenant.uuid)
        product_id = instance.id

        response = super().destroy(request, *args, **kwargs)

        self._broadcast(
            tenant_uuid=tenant_uuid,
            action="deleted",
            payload={"id": product_id},
        )

        return response

    # ==================================================
    # CUSTOM ACTIONS
    # ==================================================
    @action(detail=False, methods=["post"])
    def check_stock(self, request):
        """
        Tenant-safe stock check
        """
        tenant = self._get_user_tenant(request.user)
        if not tenant:
            return Response([], status=status.HTTP_403_FORBIDDEN)

        items = request.data.get("products", [])
        results = []

        for item in items:
            product_id = item.get("product_id")
            quantity = item.get("quantity", 1)

            try:
                product = Product.objects.get(id=product_id, tenant=tenant)
                product.auto_update_status()

                result = {
                    "product_id": product.id,
                    "product_name": product.name,
                    "stock": product.stock,
                    "status": product.status,
                    "available": True,
                }

                if product.is_expired():
                    result["available"] = False
                    result["reason"] = f"Expired on {product.expiry_date}"
                elif product.stock < quantity:
                    result["available"] = False
                    result["reason"] = "Insufficient stock"
                elif product.status == Product.STATUS_INACTIVE:
                    result["available"] = False
                    result["reason"] = "Product inactive"

                results.append(result)

            except Product.DoesNotExist:
                results.append({
                    "product_id": product_id,
                    "available": False,
                    "reason": "Product not found",
                })

        return Response({"results": results})

    @action(detail=False, methods=["get"], url_path="also-buy")
    def also_buy(self, request):
        """
        Return a balanced mix of active products across categories for cross-sell widgets.

        Query params:
        - limit: max number of products to return (default 12, max 50)
        - user_view=true/false: when true, ignores auth and uses active products (handled in get_permissions)
        """

        try:
            limit = int(request.query_params.get("limit", 12))
        except ValueError:
            limit = 12

        limit = max(1, min(limit, 50))

        # Source pool: active products (respect tenant for authed admins, public otherwise)
        base_qs = Product.objects.filter(status=Product.STATUS_ACTIVE)

        # For authenticated tenant users (non-user_view), restrict to their tenant
        if not request.query_params.get("user_view") == "true":
            tenant = self._get_user_tenant(request.user)
            if tenant:
                base_qs = base_qs.filter(tenant=tenant)
            else:
                base_qs = Product.objects.none()

        products = list(base_qs)
        if not products:
            return Response([], status=status.HTTP_200_OK)

        # Group by category (fallback to "Uncategorized")
        categories = {}
        for prod in products:
            cat = prod.category.strip() if prod.category else "Uncategorized"
            categories.setdefault(cat, []).append(prod)

        # Shuffle products within each category for variety
        for plist in categories.values():
            random.shuffle(plist)

        # Decide per-category pick target
        num_cats = len(categories)
        per_cat = max(1, math.ceil(limit / num_cats))

        selected = []
        # First pass: take up to per_cat from each category
        for plist in categories.values():
            take = min(per_cat, len(plist))
            selected.extend(plist[:take])

        # If still short, fill from remaining pool across categories
        if len(selected) < limit:
            remaining_pool = []
            for plist in categories.values():
                if len(plist) > per_cat:
                    remaining_pool.extend(plist[per_cat:])
            random.shuffle(remaining_pool)
            needed = limit - len(selected)
            selected.extend(remaining_pool[:needed])

        # Cap to requested limit and shuffle final list for distribution
        random.shuffle(selected)
        selected = selected[:limit]

        serializer = self.get_serializer(selected, many=True)
        return Response(serializer.data)

    # ==================================================
    # WebSocket broadcasting
    # ==================================================
    def _broadcast(self, tenant_uuid, action, payload):
        """
        Broadcast tenant-specific product updates (now using tenant_uuid)
        """
        channel_layer = get_channel_layer()

        # Always include tenant_uuid in payload for filtering on the client
        payload_with_tenant = {"tenant_uuid": tenant_uuid, **payload}

        # Tenant-specific broadcast
        async_to_sync(channel_layer.group_send)(
            f"products_tenant_{tenant_uuid}",
            {
                "type": "products.message",
                "action": action,
                "data": payload_with_tenant,
            },
        )

        # Global broadcast for public/anonymous clients
        async_to_sync(channel_layer.group_send)(
            "products",
            {
                "type": "products.message",
                "action": action,
                "data": payload_with_tenant,
            },
        )
