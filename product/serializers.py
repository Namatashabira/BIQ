from rest_framework import serializers
from django.db import transaction

from .models import Product, ProductImage
from .image_processing import process_product_image
from core.business_config import PricingSettings


# ======================================================
# Product Image Serializer
# ======================================================
class ProductImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField(read_only=True)

    def _abs_url(self, url: str):
        request = self.context.get("request") if hasattr(self, "context") else None
        if request and url and url.startswith("/"):
            return request.build_absolute_uri(url)
        return url

    def get_currency_code(self, obj):
        try:
            return obj.tenant.pricing_settings.default_currency
        except Exception:
            return PricingSettings.default_values().get("default_currency", "USD")

    def get_currency_symbol(self, obj):
        code = self.get_currency_code(obj) or "USD"
        symbols = {
            "USD": "$",
            "EUR": "€",
            "GBP": "£",
            "KES": "Ksh",
            "NGN": "₦",
            "UGX": "USh",
            "TZS": "TSh",
            "ZAR": "R",
        }
        return symbols.get(code.upper(), code)

    def get_currency_code(self, obj):
        try:
            return obj.tenant.pricing_settings.default_currency
        except Exception:
            return PricingSettings.default_values().get("default_currency", "USD")

    def get_currency_symbol(self, obj):
        code = self.get_currency_code(obj) or "USD"
        symbols = {
            "USD": "$",
            "EUR": "€",
            "GBP": "£",
            "KES": "Ksh",
            "NGN": "₦",
            "UGX": "USh",
            "TZS": "TSh",
            "ZAR": "R",
        }
        return symbols.get(code.upper(), code)

    class Meta:
        model = ProductImage
        fields = [
            "id",
            "image",
            "image_url",
            "alt_text",
            "display_order",
        ]
        read_only_fields = ["id"]

    def get_image_url(self, obj):
        url = obj.image.url if obj.image else None
        return self._abs_url(url)


# ======================================================
# Product Serializer
# ======================================================
class ProductSerializer(serializers.ModelSerializer):
    # Legacy single image (still supported)
    image = serializers.ImageField(required=False, allow_null=True)

    # Gallery
    images = serializers.SerializerMethodField(read_only=True)
    product_images = ProductImageSerializer(many=True, read_only=True)

    # Currency (tenant pricing settings)
    currency_code = serializers.SerializerMethodField(read_only=True)
    currency_symbol = serializers.SerializerMethodField(read_only=True)

    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def _abs_url(self, url: str):
        request = self.context.get("request") if hasattr(self, "context") else None
        if request and url and url.startswith("/"):
            return request.build_absolute_uri(url)
        return url

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "short_description",
            "full_description",
            "price",
            "retail_price",
            "wholesale_price",
            "category",

            "image",
            "images",
            "product_images",
            "image_display_style",

            "stock",
            "status",
            "manually_inactivated",

            "currency_code",
            "currency_symbol",

            "expiry_date",
            "manufacture_date",
            "batch_number",
            "supplier",

            "benefits",
            "growing_requirements",
            "ingredients",
            "directions",
            "display_settings",
            "custom_fields",

            "created_at",
            "updated_at",
        ]

        extra_kwargs = {
            "name": {"required": True},
            "description": {"required": False, "allow_blank": True},
            "short_description": {"required": False, "allow_blank": True},
            "full_description": {"required": False, "allow_blank": True},
            "category": {"required": False, "allow_blank": True},
            "image": {"required": False, "allow_null": True},
            "status": {"required": False},
            "stock": {"required": False},
        }

    # ==================================================
    # CREATE
    # ==================================================
    def create(self, validated_data):
        request = self.context.get("request")

        # Avoid saving raw image; it will be processed and attached separately
        validated_data.pop("image", None)

        with transaction.atomic():
            product = Product.objects.create(**validated_data)

            if request:
                self._handle_image_upload(product, request)

        return product

    # ==================================================
    # UPDATE
    # ==================================================
    def update(self, instance, validated_data):
        request = self.context.get("request")

        # Support clearing the legacy image field while avoiding double save of raw data
        clear_image = False
        if "image" in validated_data:
            if validated_data.get("image") is None:
                clear_image = True
            validated_data.pop("image", None)

        with transaction.atomic():
            instance = super().update(instance, validated_data)

            if clear_image:
                instance.image = None
                instance.save(update_fields=["image"])
                ProductImage.objects.filter(product=instance, display_order=0).delete()

            if request:
                self._handle_image_upload(instance, request)

        return instance

    # ==================================================
    # IMAGE HANDLING
    # ==================================================
    def _handle_image_upload(self, product, request):
        """
        Handles:
        - legacy single 'image'
        - multiple images via images[] or images[0]
        """

        has_new_images = False

        # -----------------------------------------
        # Legacy single image
        # -----------------------------------------
        single_image = request.FILES.get("image")
        if single_image:
            processed_single = process_product_image(single_image)
            product.image = processed_single
            product.save(update_fields=["image"])

            ProductImage.objects.filter(
                product=product, display_order=0
            ).delete()

            ProductImage.objects.create(
                product=product,
                image=processed_single,
                display_order=0,
            )

            has_new_images = True

        # -----------------------------------------
        # Multiple images (images[] or images[index])
        # -----------------------------------------
        image_files = request.FILES.getlist("images[]")

        if not image_files:
            image_files = []
            idx = 0
            while f"images[{idx}]" in request.FILES:
                image_files.append(request.FILES[f"images[{idx}]"])
                idx += 1

        if image_files:
            has_new_images = True

            ProductImage.objects.filter(product=product).delete()

            for index, image_file in enumerate(image_files):
                processed_file = process_product_image(image_file)
                ProductImage.objects.create(
                    product=product,
                    image=processed_file,
                    display_order=index,
                )

        # -----------------------------------------
        # Cache gallery URLs (optional compatibility)
        # -----------------------------------------
        if has_new_images:
            product.refresh_from_db()
            urls = [
                pi.image.url
                for pi in product.product_images.all().order_by(
                    "display_order", "created_at"
                )
                if pi.image
            ]

            product.images = urls
            product.save(update_fields=["images"])

    # ==================================================
    # SERIALIZED GALLERY
    # ==================================================
    def get_images(self, obj):
        gallery = obj.product_images.all().order_by(
            "display_order", "created_at"
        )

        if gallery.exists():
            return [self._abs_url(pi.image.url) for pi in gallery if pi.image]

        return [self._abs_url(url) for url in (obj.images or [])]

    # Currency helpers for SerializerMethodField
    def get_currency_code(self, obj):
        try:
            return obj.tenant.pricing_settings.default_currency
        except Exception:
            return PricingSettings.default_values().get("default_currency", "USD")

    def get_currency_symbol(self, obj):
        code = self.get_currency_code(obj) or "USD"
        symbols = {
            "USD": "$",
            "EUR": "€",
            "GBP": "£",
            "KES": "Ksh",
            "NGN": "₦",
            "UGX": "USh",
            "TZS": "TSh",
            "ZAR": "R",
        }
        return symbols.get(code.upper(), code)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Ensure primary image URL is absolute when served from a different host/port than the frontend
        data["image"] = self._abs_url(data.get("image"))
        return data
