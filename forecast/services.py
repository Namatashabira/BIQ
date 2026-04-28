# forecast/services.py

from decimal import Decimal
from datetime import timedelta
from django.utils.timezone import now
from django.db.models import Sum
from core.models import Order

# -----------------------------
# 1. MULTIPLIER CONSTANTS
# -----------------------------

LEVEL_MULTIPLIERS = {
    "HIGH": Decimal("1.25"),
    "MEDIUM": Decimal("1.00"),
    "LOW": Decimal("0.75"),
}

# -----------------------------
# 2. SECTOR SEASONALITY (MONTHLY)
# -----------------------------

SECTOR_MONTHLY_FACTORS = {
    "agriculture_crops": {
        1: 1.25, 2: 1.25, 3: 0.75, 4: 0.75, 5: 1.00,
        6: 1.25, 7: 1.25, 8: 1.00, 9: 0.75, 10: 0.75,
        11: 1.25, 12: 1.25,
    },
    "poultry": {
        1: 1.00, 2: 1.00, 3: 1.25, 4: 1.25,
        5: 1.00, 6: 1.00, 7: 1.00, 8: 1.00,
        9: 1.00, 10: 1.00, 11: 1.25, 12: 1.25,
    },
    "pharmacy": {
        1: 1.00, 2: 1.00, 3: 1.25, 4: 1.25,
        5: 1.25, 6: 1.00, 7: 1.00, 8: 1.00,
        9: 1.25, 10: 1.25, 11: 1.25, 12: 1.00,
    },
    "grocery": {
        1: 0.75, 2: 1.00, 3: 1.00, 4: 1.25,
        5: 1.00, 6: 1.00, 7: 1.00, 8: 1.00,
        9: 1.00, 10: 1.25, 11: 1.25, 12: 1.25,
    },
    "restaurant": {
        1: 1.00, 2: 1.00, 3: 1.00, 4: 1.25,
        5: 1.00, 6: 1.00, 7: 1.00, 8: 1.25,
        9: 1.00, 10: 1.00, 11: 1.00, 12: 1.25,
    },
    "clothing": {
        1: 0.75, 2: 0.75, 3: 1.25, 4: 1.25,
        5: 1.00, 6: 1.00, 7: 1.25, 8: 1.25,
        9: 1.00, 10: 1.00, 11: 1.25, 12: 1.25,
    },
    "wholesale": {
        1: 0.75, 2: 1.00, 3: 1.00, 4: 1.25,
        5: 1.00, 6: 1.00, 7: 1.00, 8: 1.00,
        9: 1.25, 10: 1.25, 11: 1.25, 12: 1.25,
    },
    "hardware": {
        1: 1.25, 2: 1.25, 3: 1.00, 4: 1.00,
        5: 1.00, 6: 1.25, 7: 1.25, 8: 1.25,
        9: 0.75, 10: 0.75, 11: 0.75, 12: 1.00,
    },
    "education": {
        1: 1.25, 2: 1.25, 3: 0.75, 4: 0.75,
        5: 1.25, 6: 0.75, 7: 0.75, 8: 0.75,
        9: 1.25, 10: 0.75, 11: 0.75, 12: 0.75,
    },
}

# -----------------------------
# 3. POST-HARVEST SCARCITY (AGRICULTURE)
# -----------------------------

POST_HARVEST_SCARCITY = {
    "agriculture_crops": {
        8: Decimal("1.10"),
        9: Decimal("1.15"),
        10: Decimal("1.10"),
    }
}

# -----------------------------
# 4. UNIVERSAL UGANDA TRIGGERS
# -----------------------------

def universal_triggers(month: int) -> Decimal:
    factor = Decimal("1.00")

    # School reopening
    if month in (1, 5, 9):
        factor *= Decimal("1.10")

    # Rainy season start
    if month in (3, 9):
        factor *= Decimal("1.08")

    # Festive seasons
    if month in (4, 12):
        factor *= Decimal("1.15")

    return factor

# -----------------------------
# 5. SALARY CYCLE (25th–5th)
# -----------------------------

def salary_cycle_factor(day: int) -> Decimal:
    if day >= 25 or day <= 5:
        return Decimal("1.15")
    return Decimal("1.00")

# -----------------------------
# 6. BASELINE FROM RECENT SALES
# -----------------------------

def get_recent_sales_baseline(business, weeks=8) -> Decimal:
    end_date = now()
    start_date = end_date - timedelta(weeks=weeks)

    tenant = getattr(business.owner, 'tenant', None)
    if not tenant:
        from tenants.models import Tenant
        tenant = Tenant.objects.filter(admin=business.owner).first()
    if not tenant:
        return Decimal("0")

    total = (
        Order.objects.filter(
            tenant=tenant,
            status__in=["confirmed", "delivered"],
            date__range=[start_date, end_date],
        )
        .aggregate(total=Sum("total"))["total"]
        or Decimal("0")
    )

    if total == 0:
        return Decimal("0")

    return (total / weeks).quantize(Decimal("0.01"))

# -----------------------------
# 7. RECENT TREND (MOVING AVG)
# -----------------------------

def recent_trend_forecast(business, weeks=4) -> Decimal:
    end_date = now()
    start_date = end_date - timedelta(weeks=weeks)

    tenant = getattr(business.owner, 'tenant', None)
    if not tenant:
        from tenants.models import Tenant
        tenant = Tenant.objects.filter(admin=business.owner).first()
    if not tenant:
        return Decimal("0")

    total = (
        Order.objects.filter(
            tenant=tenant,
            status__in=["confirmed", "delivered"],
            date__range=[start_date, end_date],
        )
        .aggregate(total=Sum("total"))["total"]
        or Decimal("0")
    )

    if total == 0:
        return Decimal("0")

    return (total / weeks).quantize(Decimal("0.01"))

# -----------------------------
# 8. RESTOCK WINDOWS (SECTOR)
# -----------------------------

RESTOCK_WINDOWS = {
    "agriculture_crops": "6–10 weeks before harvest peak",
    "poultry": "8 weeks before festive season",
    "pharmacy": "3–4 weeks before rainy season",
    "grocery": "2–3 weeks before salary/festive peak",
    "restaurant": "1–2 weeks before weekends/holidays",
    "clothing": "4–6 weeks before festivals",
    "wholesale": "6 weeks before retail peaks",
    "hardware": "4–6 weeks before dry season",
    "education": "3–4 weeks before school opening",
}

# -----------------------------
# 9. BUSINESS TYPE TO SECTOR MAPPING
# -----------------------------

BUSINESS_TYPE_TO_SECTOR = {
    "retail": "grocery",
    "wholesale": "wholesale",
    "supermarket": "grocery",
    "restaurant": "restaurant",
    "manufacturing": "hardware",
    "service": "restaurant",  # Generic service
    "health": "pharmacy",
    "education": "education",
    "agriculture": "agriculture_crops",
    "hardware": "hardware",
    "transport": "hardware",  # Generic
    "ecommerce": "grocery",   # Generic online
    "nonprofit": "grocery",   # Generic
    "other": "grocery",       # Default
}

# -----------------------------
# 10. BUSINESS TYPE PRODUCT SUGGESTIONS
# -----------------------------

BUSINESS_TYPE_PRODUCTS = {
    "retail": [
        {"name": "Premium T-Shirts", "category": "Clothing", "retail_split": 80, "wholesale_split": 20},
        {"name": "Designer Jeans", "category": "Clothing", "retail_split": 75, "wholesale_split": 25},
        {"name": "Running Shoes", "category": "Footwear", "retail_split": 85, "wholesale_split": 15},
        {"name": "Smartphone Cases", "category": "Accessories", "retail_split": 70, "wholesale_split": 30},
        {"name": "Wireless Earbuds", "category": "Electronics", "retail_split": 90, "wholesale_split": 10},
    ],
    "supermarket": [
        {"name": "Fresh Milk", "category": "Dairy", "retail_split": 95, "wholesale_split": 5},
        {"name": "Organic Bread", "category": "Bakery", "retail_split": 90, "wholesale_split": 10},
        {"name": "Fresh Vegetables", "category": "Produce", "retail_split": 85, "wholesale_split": 15},
        {"name": "Premium Coffee", "category": "Beverages", "retail_split": 80, "wholesale_split": 20},
        {"name": "Frozen Pizza", "category": "Frozen Foods", "retail_split": 88, "wholesale_split": 12},
    ],
    "restaurant": [
        {"name": "Grilled Chicken", "category": "Main Course", "retail_split": 100, "wholesale_split": 0},
        {"name": "Caesar Salad", "category": "Appetizers", "retail_split": 100, "wholesale_split": 0},
        {"name": "Chocolate Cake", "category": "Desserts", "retail_split": 100, "wholesale_split": 0},
        {"name": "Craft Beer", "category": "Beverages", "retail_split": 100, "wholesale_split": 0},
        {"name": "Margherita Pizza", "category": "Main Course", "retail_split": 100, "wholesale_split": 0},
    ],
    "agriculture": [
        {"name": "Premium Seeds", "category": "Seeds", "retail_split": 60, "wholesale_split": 40},
        {"name": "Organic Fertilizer", "category": "Fertilizers", "retail_split": 45, "wholesale_split": 55},
        {"name": "Herbicide Pro", "category": "Pesticides", "retail_split": 70, "wholesale_split": 30},
        {"name": "Irrigation Pipes", "category": "Equipment", "retail_split": 55, "wholesale_split": 45},
        {"name": "Crop Protection Net", "category": "Equipment", "retail_split": 65, "wholesale_split": 35},
    ],
    "hardware": [
        {"name": "Power Drill", "category": "Tools", "retail_split": 75, "wholesale_split": 25},
        {"name": "Paint Brushes Set", "category": "Painting", "retail_split": 80, "wholesale_split": 20},
        {"name": "Steel Nails", "category": "Fasteners", "retail_split": 40, "wholesale_split": 60},
        {"name": "PVC Pipes", "category": "Plumbing", "retail_split": 50, "wholesale_split": 50},
        {"name": "LED Light Bulbs", "category": "Electrical", "retail_split": 85, "wholesale_split": 15},
    ],
    "health": [
        {"name": "Blood Pressure Monitor", "category": "Medical Devices", "retail_split": 90, "wholesale_split": 10},
        {"name": "Vitamin Supplements", "category": "Supplements", "retail_split": 95, "wholesale_split": 5},
        {"name": "First Aid Kit", "category": "Emergency", "retail_split": 85, "wholesale_split": 15},
        {"name": "Face Masks", "category": "PPE", "retail_split": 80, "wholesale_split": 20},
        {"name": "Thermometer", "category": "Medical Devices", "retail_split": 88, "wholesale_split": 12},
    ],
    "education": [
        {"name": "Textbooks", "category": "Books", "retail_split": 95, "wholesale_split": 5},
        {"name": "Notebooks", "category": "Stationery", "retail_split": 90, "wholesale_split": 10},
        {"name": "School Uniforms", "category": "Clothing", "retail_split": 85, "wholesale_split": 15},
        {"name": "Art Supplies", "category": "Materials", "retail_split": 80, "wholesale_split": 20},
        {"name": "Laptops", "category": "Technology", "retail_split": 92, "wholesale_split": 8},
    ],
    "wholesale": [
        {"name": "Bulk Rice", "category": "Grains", "retail_split": 20, "wholesale_split": 80},
        {"name": "Industrial Cleaning Supplies", "category": "Chemicals", "retail_split": 15, "wholesale_split": 85},
        {"name": "Packaging Materials", "category": "Packaging", "retail_split": 25, "wholesale_split": 75},
        {"name": "Raw Materials", "category": "Industrial", "retail_split": 10, "wholesale_split": 90},
        {"name": "Bulk Beverages", "category": "Drinks", "retail_split": 30, "wholesale_split": 70},
    ],
    "ecommerce": [
        {"name": "Wireless Headphones", "category": "Electronics", "retail_split": 85, "wholesale_split": 15},
        {"name": "Smart Home Devices", "category": "IoT", "retail_split": 90, "wholesale_split": 10},
        {"name": "Fitness Trackers", "category": "Wearables", "retail_split": 88, "wholesale_split": 12},
        {"name": "Gaming Accessories", "category": "Gaming", "retail_split": 82, "wholesale_split": 18},
        {"name": "Home Decor", "category": "Lifestyle", "retail_split": 87, "wholesale_split": 13},
    ],
    "manufacturing": [
        {"name": "Raw Materials", "category": "Industrial", "retail_split": 20, "wholesale_split": 80},
        {"name": "Machine Parts", "category": "Components", "retail_split": 15, "wholesale_split": 85},
        {"name": "Industrial Tools", "category": "Equipment", "retail_split": 25, "wholesale_split": 75},
        {"name": "Safety Equipment", "category": "PPE", "retail_split": 30, "wholesale_split": 70},
        {"name": "Quality Control Devices", "category": "Testing", "retail_split": 35, "wholesale_split": 65},
    ],
    "transport": [
        {"name": "Vehicle Parts", "category": "Auto Parts", "retail_split": 60, "wholesale_split": 40},
        {"name": "Tires", "category": "Auto", "retail_split": 55, "wholesale_split": 45},
        {"name": "Fuel Additives", "category": "Chemicals", "retail_split": 40, "wholesale_split": 60},
        {"name": "Car Accessories", "category": "Auto", "retail_split": 75, "wholesale_split": 25},
        {"name": "Maintenance Tools", "category": "Tools", "retail_split": 65, "wholesale_split": 35},
    ],
    "nonprofit": [
        {"name": "Educational Materials", "category": "Resources", "retail_split": 100, "wholesale_split": 0},
        {"name": "Community Supplies", "category": "Aid", "retail_split": 100, "wholesale_split": 0},
        {"name": "Fundraising Items", "category": "Merchandise", "retail_split": 100, "wholesale_split": 0},
        {"name": "Training Materials", "category": "Education", "retail_split": 100, "wholesale_split": 0},
        {"name": "Event Supplies", "category": "Logistics", "retail_split": 100, "wholesale_split": 0},
    ],
    "other": [
        {"name": "General Supplies", "category": "Miscellaneous", "retail_split": 70, "wholesale_split": 30},
        {"name": "Office Materials", "category": "Stationery", "retail_split": 75, "wholesale_split": 25},
        {"name": "Basic Tools", "category": "Equipment", "retail_split": 65, "wholesale_split": 35},
        {"name": "Consumables", "category": "Supplies", "retail_split": 80, "wholesale_split": 20},
        {"name": "Accessories", "category": "General", "retail_split": 85, "wholesale_split": 15},
    ],
}

# -----------------------------
# 11. SUGGESTED PRODUCTS FUNCTION
# -----------------------------

def get_suggested_products(business_type: str, forecast_sales: Decimal) -> list:
    """
    Get suggested products based on business type with forecasted values.
    """
    products = BUSINESS_TYPE_PRODUCTS.get(business_type, BUSINESS_TYPE_PRODUCTS["other"])

    # Calculate total forecast to distribute among products
    total_forecast = float(forecast_sales)

    suggested_products = []
    for i, product in enumerate(products[:5]):  # Top 5 products
        # Distribute forecast sales among products (weighted by position)
        weights = [0.25, 0.20, 0.18, 0.15, 0.12]  # Weights for top 5 products
        product_forecast = total_forecast * weights[i]

        # Estimate units based on average price (assume $50-200 per unit)
        avg_price = 125  # Average price assumption
        estimated_units = max(1, int(product_forecast / avg_price))

        suggested_products.append({
            "name": product["name"],
            "forecast": round(product_forecast, 2),
            "units": estimated_units,
            "retailSplit": product["retail_split"],
            "wholesaleSplit": product["wholesale_split"],
        })

    return suggested_products

# -----------------------------
# 9. FINAL FORECAST ENGINE
# -----------------------------

def forecast_sales(business, business_type: str, target_month: int) -> dict:
    today = now()

    # Map business_type to sector for forecasting
    sector = BUSINESS_TYPE_TO_SECTOR.get(business_type, "grocery")

    # --- Baseline & recent trend
    baseline = get_recent_sales_baseline(business)
    recent_trend = recent_trend_forecast(business)

    # --- Calendar factors
    sector_factor = Decimal(
        SECTOR_MONTHLY_FACTORS.get(sector, {}).get(target_month, 1.00)
    )
    scarcity_factor = POST_HARVEST_SCARCITY.get(sector, {}).get(
        target_month, Decimal("1.00")
    )
    universal_factor = universal_triggers(target_month)
    salary_factor = salary_cycle_factor(today.day)

    # --- Adjusted calendar forecast
    calendar_adjusted = (
        baseline
        * sector_factor
        * scarcity_factor
        * universal_factor
        * salary_factor
    )

    # --- Blend with recent trend
    final_forecast = (
        (recent_trend * Decimal("0.65"))
        + (calendar_adjusted * Decimal("0.35"))
    ).quantize(Decimal("0.01"))

    # --- Restock logic
    restock_required = sector_factor >= Decimal("1.20")
    restock_window = RESTOCK_WINDOWS.get(sector) if restock_required else None

    # --- Sales increase hints
    sales_increase_reasons = []

    if sector_factor >= Decimal("1.20"):
        sales_increase_reasons.append("Peak seasonal demand for this sector.")
    if scarcity_factor > Decimal("1.00"):
        sales_increase_reasons.append("Post-harvest scarcity boosting prices/sales.")
    if target_month in (1, 5, 9):
        sales_increase_reasons.append("School term opening increases demand.")
    if target_month in (3, 9):
        sales_increase_reasons.append("Start of rainy season increases health/food demand.")
    if target_month in (4, 12):
        sales_increase_reasons.append("Festive season boosts consumption.")
    if salary_factor > Decimal("1.00"):
        sales_increase_reasons.append("End-of-month salary payments likely increase purchases.")

    # --- Human-readable summary
    summary = (
        "Sales expected to increase due to: " + ", ".join(sales_increase_reasons)
        if sales_increase_reasons else "No major seasonal sales increase expected."
    )

    # --- Get suggested products based on business type
    suggested_products = get_suggested_products(business_type, final_forecast)

    return {
        "baseline": baseline,
        "recent_trend": recent_trend,
        "sector_factor": sector_factor,
        "scarcity_factor": scarcity_factor,
        "universal_factor": universal_factor,
        "salary_factor": salary_factor,
        "forecast_sales": final_forecast,
        "restock_required": restock_required,
        "restock_window": restock_window,
        "sales_increase_hints": sales_increase_reasons,
        "summary": summary,
        "suggested_products": suggested_products,
    }
