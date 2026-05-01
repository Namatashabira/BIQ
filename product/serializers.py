import json
from rest_framework import serializers
from django.db import transaction

from .models import Product, ProductImage
from core.business_config import PricingSettings


class FlexibleJSONField(serializers.JSONField):
    """Accepts already-parsed JSON, JSON strings, or QueryDict lists (multipart/form-data)."""
    def to_internal_value(self, data):
        if isinstance(data, list):
            data = data[0] if data else ''
        if isinstance(data, str):
            data = data.strip()
            if not data or data == 'null':
                return self._empty_default()
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, ValueError):
                self.fail('invalid')
        return super().to_internal_value(data)

    def _empty_default(self):
        default = self.default
        if callable(default):
            return default()
        return default if default is not serializers.empty else None


def _abs_url(url, request=None):
    """Return Cloudinary (https) URLs as-is; only prepend host for relative paths."""
    if not url:
        return url
    if url.startswith('http://') or url.startswith('https://'):
        return url
    if request and url.startswith('/'):
        return request.build_absolute_uri(url)
    return url


CURRENCY_SYMBOLS = {
    "USD": "$", "EUR": "€", "GBP": "£",
    "KES": "Ksh", "NGN": "₦", "UGX": "USh",
    "TZS": "TSh", "ZAR": "R",
}


def _get_currency(obj):
    try:
        code = obj.tenant.pricing_settings.default_currency
    except Exception:
        code = PricingSettings.default_values().get("default_currency", "USD")
    return code or "USD"


# ======================================================
# Product Image Serializer
# ======================================================
class ProductImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ProductImage
        fields = ["id", "image", "image_url", "alt_text", "display_order"]
        read_only_fields = ["id"]

    def get_image_url(self, obj):
        try:
            return _abs_url(obj.image.url, self.context.get("request"))
        except Exception:
            return None


# ======================================================
# Product Serializer
# ======================================================
class ProductSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField(read_only=True)
    images = serializers.SerializerMethodField(read_only=True)
    product_images = ProductImageSerializer(many=True, read_only=True)

    currency_code = serializers.SerializerMethodField(read_only=True)
    currency_symbol = serializers.SerializerMethodField(read_only=True)

    benefits = FlexibleJSONField(required=False, default=list)
    growing_requirements = FlexibleJSONField(required=False, default=list)
    ingredients = FlexibleJSONField(required=False, default=list)
    directions = FlexibleJSONField(required=False, default=list)
    display_settings = FlexibleJSONField(required=False, default=dict)
    custom_fields = FlexibleJSONField(required=False, default=dict)

    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "name", "description", "short_description", "full_description",
            "price", "retail_price", "wholesale_price", "category",
            "image", "images", "product_images", "image_display_style",
            "stock", "status", "manually_inactivated",
            "currency_code", "currency_symbol",
            "expiry_date", "manufacture_date", "date_stocked", "batch_number", "supplier",
            "benefits", "growing_requirements", "ingredients", "directions",
            "display_settings", "custom_fields",
            "created_at", "updated_at",
        ]
        extra_kwargs = {
            "name": {"required": False, "allow_blank": True},
            "description": {"required": False, "allow_blank": True},
            "short_description": {"required": False, "allow_blank": True},
            "full_description": {"required": False, "allow_blank": True},
            "category": {"required": False, "allow_blank": True},
            "status": {"required": False},
            "stock": {"required": False},
            "price": {"required": False},
            "retail_price": {"required": False},
            "wholesale_price": {"required": False},
            "expiry_date": {"required": False, "allow_null": True},
            "manufacture_date": {"required": False, "allow_null": True},
            "date_stocked": {"required": False, "allow_null": True},
            "batch_number": {"required": False, "allow_blank": True},
            "supplier": {"required": False, "allow_blank": True},
            "image_display_style": {"required": False},
            "manually_inactivated": {"required": False},
        }

    # --------------------------------------------------
    # Field getters
    # --------------------------------------------------
    def get_image(self, obj):
        try:
            return obj.image.url if obj.image else None
        except Exception:
            return None

    def get_images(self, obj):
        request = self.context.get("request")
        gallery = obj.product_images.all().order_by("display_order", "created_at")
        if gallery.exists():
            return [_abs_url(pi.image.url, request) for pi in gallery if pi.image]
        return [_abs_url(url, request) for url in (obj.images or [])]

    def get_currency_code(self, obj):
        return _get_currency(obj)

    def get_currency_symbol(self, obj):
        return CURRENCY_SYMBOLS.get(_get_currency(obj).upper(), _get_currency(obj))

    # --------------------------------------------------
    # CREATE
    # --------------------------------------------------
    def create(self, validated_data):
        validated_data.setdefault("name", "Untitled Product")

        tenant = validated_data.get("tenant")
        if tenant is None:
            raise serializers.ValidationError(
                {"tenant": "Tenant could not be resolved. Ensure you are authenticated and associated with a tenant."}
            )

        with transaction.atomic():
            product = Product.objects.create(**validated_data)
        return product

    # --------------------------------------------------
    # UPDATE
    # --------------------------------------------------
    def update(self, instance, validated_data):
        with transaction.atomic():
            instance = super().update(instance, validated_data)
        return instance
