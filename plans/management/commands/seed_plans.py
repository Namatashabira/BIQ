from django.core.management.base import BaseCommand
from plans.models import Plan

PLANS = [
    {
        'key': 'free',
        'name': 'Free Trial',
        'price_ugx': 0,
        'trial_days': 14,
        'product_limit': 7,
        'allowed_pages': [
            'dashboard_enabled', 'product_enabled', 'inventory_enabled',
            'orders_enabled', 'manual_entry_enabled', 'payments_enabled',
        ],
    },
    {
        'key': 'starter',
        'name': 'Starter',
        'price_ugx': 80000,
        'trial_days': 0,
        'product_limit': -1,
        'allowed_pages': [
            'dashboard_enabled', 'product_enabled', 'inventory_enabled',
            'orders_enabled', 'manual_entry_enabled', 'payments_enabled', 'sales_enabled',
        ],
    },
    {
        'key': 'business',
        'name': 'Business',
        'price_ugx': 150000,
        'trial_days': 0,
        'product_limit': -1,
        'allowed_pages': [
            'dashboard_enabled', 'product_enabled', 'inventory_enabled',
            'orders_enabled', 'manual_entry_enabled', 'payments_enabled',
            'sales_enabled', 'customers_enabled', 'analytics_enabled',
            'ai_insights_enabled', 'accounting_enabled',
        ],
    },
    {
        'key': 'enterprise',
        'name': 'Enterprise',
        'price_ugx': 400000,
        'trial_days': 0,
        'product_limit': -1,
        'allowed_pages': [],
    },
]


class Command(BaseCommand):
    help = 'Seed default subscription plans'

    def handle(self, *args, **kwargs):
        for data in PLANS:
            plan, created = Plan.objects.update_or_create(
                key=data['key'],
                defaults=data,
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(self.style.SUCCESS(f'{action}: {plan.name}'))
