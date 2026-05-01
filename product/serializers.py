import json
from rest_framework import serializers
from django.db import transaction

from .models import Product, ProductImage
from .image_processing import process_product_image
from core.business_config import PricingSettings


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
    # image is read-only (Cloudinary URL string); uploads go through image_upload
    image = serializers.SerializerMethodField(read_only=True)
    image_upload = serializers.ImageField(required=False, allow_null=True, write_only=True)

    images = serializers.SerializerMethodField(read_only=True)
    product_images = ProductImageSerializer(many=True, read_only=True)

    currency_code = serializers.SerializerMethodField(read_only=True)
    currency_symbol = serializers.SerializerMethodField(read_only=True)

    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "name", "description", "short_description", "full_description",
            "price", "retail_price", "wholesale_price", "category",
            "image", "image_upload", "images", "product_images", "image_display_style",
            "stock", "status", "manually_inactivated",
            "currency_code", "currency_symbol",
            "expiry_date", "manufacture_date", "batch_number", "supplier",
            "benefits", "growing_requirements", "ingredients", "directions",
            "display_settings", "custom_fields",
            "created_at", "updated_at",
        ]
        extra_kwargs = {
            "name": {"required": True},
            "description": {"required": False, "allow_blank": True},
            "short_description": {"required": False, "allow_blank": True},
            "full_description": {"required": False, "allow_blank": True},
            "category": {"required": False, "allow_blank": True},
            "status": {"required": False},
            "stock": {"required": False},
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
    # Parse JSON string fields from multipart/form-data
    # --------------------------------------------------
    JSON_FIELDS = ["benefits", "growing_requirements", "ingredients", "directions", "display_settings", "custom_fields"]

    def to_internal_value(self, data):
        mutable = data.copy() if hasattr(data, "copy") else dict(data)
        for field in self.JSON_FIELDS:
            if field in mutable and isinstance(mutable[field], str):
                try:
                    mutable[field] = json.loads(mutable[field])
                except (json.JSONDecodeError, ValueError):
                    pass
        return super().to_internal_value(mutable)

    # --------------------------------------------------
    # CREATE
    # --------------------------------------------------
    def create(self, validated_data):
        validated_data.pop("image_upload", None)
        request = self.context.get("request")
        with transaction.atomic():
            product = Product.objects.create(**validated_data)
            if request:
                self._handle_image_upload(product, request)
        return product

    # --------------------------------------------------
    # UPDATE
    # --------------------------------------------------
    def update(self, instance, validated_data):
        request = self.context.get("request")
        clear_image = validated_data.pop("image_upload", None) is None and "image_upload" in self.initial_data

        with transaction.atomic():
            instance = super().update(instance, validated_data)

            if clear_image:
                instance.image = None
                instance.save(update_fields=["image"])
                ProductImage.objects.filter(product=instance, display_order=0).delete()

            if request:
                self._handle_image_upload(instance, request)

        return instance

    # --------------------------------------------------
    # IMAGE UPLOAD HANDLER
    # --------------------------------------------------
    def _handle_image_upload(self, product, request):
        has_new_images = False

        # Single image — accepts both 'image' and 'image_upload' keys
        single_image = request.FILES.get("image") or request.FILES.get("image_upload")
        if single_image:
            processed = process_product_image(single_image)
            product.image = processed
            product.save(update_fields=["image"])
            ProductImage.objects.filter(product=product, display_order=0).delete()
            ProductImage.objects.create(product=product, image=processed, display_order=0)
            has_new_images = True

        # Multiple images — images[] or images[0], images[1], ...
        image_files = request.FILES.getlist("images[]")
        if not image_files:
            image_files, idx = [], 0
            while f"images[{idx}]" in request.FILES:
                image_files.append(request.FILES[f"images[{idx}]"])
                idx += 1

        if image_files:
            has_new_images = True
            ProductImage.objects.filter(product=product).delete()
            for index, image_file in enumerate(image_files):
                processed_file = process_product_image(image_file)
                ProductImage.objects.create(
                    product=product, image=processed_file, display_order=index
                )

        # Cache gallery URLs in the JSON field for quick access
        if has_new_images:
            product.refresh_from_db()
            urls = [
                pi.image.url
                for pi in product.product_images.all().order_by("display_order", "created_at")
                if pi.image
            ]
            product.images = urls
            product.save(update_fields=["images"])
