# core/constants.py
from enum import Enum

class BusinessType(str, Enum):
    RETAIL = "retail"
    WHOLESALE = "wholesale"
    SUPERMARKET = "supermarket"
    RESTAURANT = "restaurant"
    MANUFACTURING = "manufacturing"
    SERVICE = "service"
    HEALTH = "health"
    EDUCATION = "education"
    AGRICULTURE = "agriculture"
    HARDWARE = "hardware"
    TRANSPORT = "transport"
    ECOMMERCE = "ecommerce"
    NONPROFIT = "nonprofit"
    OTHER = "other"

BUSINESS_TYPE_CHOICES = [
    (BusinessType.RETAIL, "Retail / Shop"),
    (BusinessType.WHOLESALE, "Wholesale / Distribution"),
    (BusinessType.SUPERMARKET, "Supermarket / Grocery"),
    (BusinessType.RESTAURANT, "Restaurant / Food & Beverage"),
    (BusinessType.MANUFACTURING, "Manufacturing"),
    (BusinessType.SERVICE, "Service Business"),
    (BusinessType.HEALTH, "Health / Medical"),
    (BusinessType.EDUCATION, "Education / School"),
    (BusinessType.AGRICULTURE, "Agriculture / Agribusiness"),
    (BusinessType.HARDWARE, "Hardware / Construction"),
    (BusinessType.TRANSPORT, "Transportation / Logistics"),
    (BusinessType.ECOMMERCE, "E-commerce / Online Business"),
    (BusinessType.NONPROFIT, "Non-Profit / NGO"),
    (BusinessType.OTHER, "Other"),
]

BUSINESS_TYPE_DEFAULT_FEATURES = {
    BusinessType.RETAIL: ["stock", "pos", "receipts"],
    BusinessType.EDUCATION: ["fees", "students", "classes"],
    BusinessType.HEALTH: ["patients", "appointments"],
    BusinessType.RESTAURANT: ["menu", "kitchen_orders"],
    BusinessType.SERVICE: ["invoices", "projects"],
}
