"""
Fix tenants whose BusinessConfig.business_type is 'other' but Tenant.business_type is correct.
Also re-applies the preset for those tenants.

Run: python manage.py fix_school_config
Run: python manage.py fix_school_config --dry-run
Run: python manage.py fix_school_config --business-type school
"""
from django.core.management.base import BaseCommand
from tenants.models import Tenant
from core.business_config import BusinessConfig


class Command(BaseCommand):
    help = 'Fix BusinessConfig.business_type mismatch and re-apply presets'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show what would be fixed without making changes')
        parser.add_argument('--business-type', default=None, help='Only fix tenants of this type (e.g. school)')
        parser.add_argument('--force', action='store_true', help='Re-apply preset even if already applied')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        filter_type = options['business_type']
        force = options['force']

        tenants = Tenant.objects.all().select_related('business_config')
        if filter_type:
            tenants = tenants.filter(business_type=filter_type)

        fixed = 0
        for tenant in tenants:
            try:
                config = tenant.business_config
            except BusinessConfig.DoesNotExist:
                self.stdout.write(f'  [CREATE] {tenant.name} — no BusinessConfig, creating with type={tenant.business_type}')
                if not dry_run:
                    config = BusinessConfig.objects.create(
                        tenant=tenant,
                        business_type=tenant.business_type or 'other',
                        onboarding_completed=True,
                    )
                    config.apply_business_preset(force=True)
                fixed += 1
                continue

            needs_fix = False

            # Fix mismatched business_type
            if config.business_type != tenant.business_type and tenant.business_type:
                self.stdout.write(
                    f'  [FIX TYPE] {tenant.name}: config={config.business_type} -> tenant={tenant.business_type}'
                )
                if not dry_run:
                    config.business_type = tenant.business_type
                    config.preset_applied = False  # force re-apply
                    config.save(update_fields=['business_type', 'preset_applied'])
                needs_fix = True

            # Re-apply preset if not applied or forced
            if not config.preset_applied or force or needs_fix:
                self.stdout.write(f'  [PRESET]  {tenant.name} ({config.business_type}) — applying preset')
                if not dry_run:
                    config.apply_business_preset(force=True)
                fixed += 1

        if dry_run:
            self.stdout.write(self.style.WARNING(f'\nDry run — {fixed} tenant(s) would be fixed.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\nDone — {fixed} tenant(s) fixed.'))
