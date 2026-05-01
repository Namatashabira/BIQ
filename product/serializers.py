import json
from rest_framework import serializers
from django.db import transaction

from .models import Product, ProductImage
from .image_processing import process_product_image
from core.business_config import PricingSettings


class FlexibleJSONField(serializers.JSONField):
    """Accepts already-parsed JSON, JSON strings, or QueryDict lists (multipart/form-data)."""
    def to_internal_value(self, data):
        # QueryDict wraps values as lists — unwrap
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
    # image is read-only (Cloudinary URL string); uploads go through image_upload
    image = serializers.SerializerMethodField(read_only=True)
    image_upload = serializers.ImageField(required=False, allow_null=True, write_only=True)

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
            "image", "image_upload", "images", "product_images", "image_display_style",
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
        validated_data.pop("image_upload", None)
        validated_data.setdefault("name", "Untitled Product")

        # Tenant must be injected by the view via serializer.save(tenant=tenant).
        # It arrives in validated_data because DRF's save() merges kwargs before
        # calling create(). Guard here so a missing tenant raises a clean 400
        # instead of a DB IntegrityError / 500.
        tenant = validated_data.get("tenant")
        if tenant is None:
            raise serializers.ValidationError(
                {"tenant": "Tenant could not be resolved. Ensure you are authenticated and associated with a tenant."}
            )

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
        import logging
        logger = logging.getLogger(__name__)

        has_new_images = False

        # ── Parse existing_images ────────────────────────────────────────────
        # Accepts: JSON string, plain list, empty string, "[object Object]", None
        existing_images_keep = None  # None = not sent; [] = sent but empty
        raw = request.data.get("existing_images")
        if raw is not None:
            if isinstance(raw, list):
                # Already parsed (JSON request body)
                existing_images_keep = [
                    str(u) for u in raw if isinstance(u, str) and u.startswith("http")
                ]
            elif isinstance(raw, str):
                raw = raw.strip()
                if raw and raw not in ("", "null", "undefined"):
                    try:
                        parsed = json.loads(raw)
                        if isinstance(parsed, list):
                            existing_images_keep = [
                                str(u) for u in parsed
                                if isinstance(u, str) and u.startswith("http")
                            ]
                        else:
                            existing_images_keep = []
                    except (json.JSONDecodeError, ValueError):
                        # Garbage value like "[object Object]" — treat as keep-all
                        existing_images_keep = None
                else:
                    existing_images_keep = []

        # Prune images not in the keep-list (only when keep-list was explicitly sent)
        if existing_images_keep is not None:
            for pi in product.product_images.all():
                try:
                    pi_url = pi.image.url
                except Exception:
                    pi_url = ""
                if not any(
                    pi_url in keep or keep in pi_url
                    for keep in existing_images_keep
                ):
                    pi.delete()

        # ── Collect uploaded files ────────────────────────────────────────────
        # Support: images[], images[0], images[1]…, images (plain key from FormData)
        image_files = (
            request.FILES.getlist("images[]")
            or request.FILES.getlist("images")
        )
        if not image_files:
            idx = 0
            while f"images[{idx}]" in request.FILES:
                image_files.append(request.FILES[f"images[{idx}]"])
                idx += 1

        single_image = request.FILES.get("image") or request.FILES.get("image_upload")

        # ── Multiple images ───────────────────────────────────────────────────
        if image_files:
            processed_files = []
            for image_file in image_files:
                try:
                    processed_files.append(process_product_image(image_file))
                except Exception as exc:
                    logger.error("Image processing failed for %s: %s", getattr(image_file, "name", "?"), exc)
                    raise serializers.ValidationError(
                        {"images": f"Failed to process image '{getattr(image_file, 'name', 'unknown')}': {exc}"}
                    )

            ProductImage.objects.filter(product=product).delete()
            for index, processed_file in enumerate(processed_files):
                ProductImage.objects.create(
                    product=product, image=processed_file, display_order=index
                )
            has_new_images = True

        # ── Single image (only when no multi-image batch) ─────────────────────
        elif single_image:
            try:
                processed = process_product_image(single_image)
            except Exception as exc:
                logger.error("Single image processing failed: %s", exc)
                raise serializers.ValidationError(
                    {"image": f"Failed to process image: {exc}"}
                )
            product.image = processed
            product.save(update_fields=["image"])
            ProductImage.objects.filter(product=product, display_order=0).delete()
            ProductImage.objects.create(product=product, image=processed, display_order=0)
            has_new_images = True

        # ── Cache gallery URL list on the product ─────────────────────────────
        if has_new_images or existing_images_keep is not None:
            product.refresh_from_db()
            urls = []
            for pi in product.product_images.all().order_by("display_order", "created_at"):
                try:
                    if pi.image:
                        urls.append(pi.image.url)
                except Exception:
                    pass
            product.images = urls
            product.save(update_fields=["images"])
