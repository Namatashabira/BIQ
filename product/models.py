from django.db import models
from datetime import date
from tenants.models import Tenant
from cloudinary.models import CloudinaryField


class Product(models.Model):
    """
    Multi-tenant Product model.
    Each product belongs to exactly one tenant.
    """

    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_INACTIVE, "Inactive"),
    ]

    # ==========================
    # Multi-tenant ownership
    # ==========================
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="products",
        db_index=True,
    )

    # ==========================
    # Core product info
    # ==========================
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    short_description = models.TextField(blank=True)
    full_description = models.TextField(blank=True)

    category = models.CharField(max_length=255, blank=True, default="")

    # ==========================
    # Pricing
    # ==========================
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    retail_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    wholesale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ==========================
    # Images
    # ==========================
    image = CloudinaryField(
        'image',
        folder='products',
        blank=True,
        null=True,
        help_text="Primary/featured image — stored on Cloudinary"
    )

    image_display_style = models.CharField(
        max_length=50,
        choices=[
            ("thumbnails_left", "Thumbnails on Left"),
            ("thumbnails_bottom", "Thumbnails on Bottom"),
            ("grid", "Grid Layout"),
            ("carousel", "Carousel/Slider"),
        ],
        default="thumbnails_left",
    )

    # Optional lightweight gallery metadata (URLs, ids, captions)
    images = models.JSONField(default=list, blank=True)

    # ==========================
    # Inventory & status
    # ==========================
    stock = models.PositiveIntegerField(default=0)

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
    )

    manually_inactivated = models.BooleanField(
        default=False,
        help_text="If true, product will not auto-reactivate"
    )

    # ==========================
    # Inventory management
    # ==========================
    expiry_date = models.DateField(null=True, blank=True)
    manufacture_date = models.DateField(null=True, blank=True)
    date_stocked = models.DateField(null=True, blank=True)
    batch_number = models.CharField(max_length=100, blank=True)
    supplier = models.CharField(max_length=255, blank=True)

    # ==========================
    # Extra structured content
    # ==========================
    benefits = models.JSONField(default=list, blank=True)
    growing_requirements = models.JSONField(default=list, blank=True)
    ingredients = models.JSONField(default=list, blank=True)
    directions = models.JSONField(default=list, blank=True)

    display_settings = models.JSONField(default=dict, blank=True)
    custom_fields = models.JSONField(default=dict, blank=True)

    # ==========================
    # Timestamps
    # ==========================
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ==========================
    # Model behavior
    # ==========================
    def __str__(self):
        return f"{self.name} ({self.tenant.name})"

    def is_expired(self):
        return bool(self.expiry_date and date.today() >= self.expiry_date)

    def is_out_of_stock(self):
        return self.stock <= 0

    def should_be_inactive(self):
        return self.is_expired() or self.is_out_of_stock()

    def auto_update_status(self):
        """
        Automatically update product status unless manually inactivated.
        """
        if self.manually_inactivated:
            return False

        new_status = self.STATUS_INACTIVE if self.should_be_inactive() else self.STATUS_ACTIVE

        if self.status != new_status:
            self.status = new_status
            return True

        return False

    def save(self, *args, **kwargs):
        """
        Ensure status is always correct before saving.
        """
        self.auto_update_status()
        super().save(*args, **kwargs)

    # ==========================
    # Stock operations
    # ==========================
    def deduct_stock(self, quantity, reason="Sale"):
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        if self.is_expired():
            raise ValueError("Cannot sell expired product")

        if self.stock < quantity:
            raise ValueError("Insufficient stock")

        self.stock -= quantity
        self.save(update_fields=["stock", "status", "updated_at"])
        return True

    def add_stock(self, quantity, reason="Restock"):
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        self.stock += quantity
        self.save(update_fields=["stock", "status", "updated_at"])
        return True

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="unique_product_name_per_tenant"
            )
        ]


class ProductImage(models.Model):
    """
    Dedicated model for multiple product images
    (recommended over JSON for scalability)
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="product_images",
    )

    image = CloudinaryField('image', folder='products')
    alt_text = models.CharField(max_length=255, blank=True)
    display_order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "created_at"]
        verbose_name_plural = "Product Images"

    def __str__(self):
        return f"{self.product.name} - Image {self.display_order}"
