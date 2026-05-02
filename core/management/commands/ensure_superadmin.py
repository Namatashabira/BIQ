import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Ensure the platform superadmin user exists (idempotent)'

    def handle(self, *args, **options):
        username = os.environ.get('SUPERADMIN_USERNAME', 'SSEMATAADMIN')
        password = os.environ.get('SUPERADMIN_PASSWORD', 'sabira@25')
        email    = os.environ.get('SUPERADMIN_EMAIL',    'admin@businessiq.com')
        name     = os.environ.get('SUPERADMIN_NAME',     'SSEMATA SABIRA')

        first, *rest = name.split(' ', 1)
        last = rest[0] if rest else ''

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email':        email,
                'first_name':   first,
                'last_name':    last,
                'is_staff':     True,
                'is_superuser': True,
                'is_active':    True,
                'role':         'superadmin',
            }
        )

        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(
                f'Superadmin created: {username}'
            ))
        else:
            # Always sync staff/superuser flags and role in case they drifted
            changed = False
            if not user.is_staff:      user.is_staff      = True;  changed = True
            if not user.is_superuser:  user.is_superuser  = True;  changed = True
            if not user.is_active:     user.is_active     = True;  changed = True
            if user.role != 'superadmin': user.role = 'superadmin'; changed = True
            if changed:
                user.save()
                self.stdout.write(self.style.WARNING(
                    f'Superadmin {username} flags corrected'
                ))
            else:
                self.stdout.write(f'Superadmin {username} already exists — no changes')

        # Ensure tenant exists for superadmin
        from tenants.models import Tenant
        if not user.tenant:
            tenant, _ = Tenant.objects.get_or_create(
                name='Platform Administration',
                defaults={'admin': user, 'is_verified': True}
            )
            user.tenant = tenant
            user.save(update_fields=['tenant'])
            self.stdout.write(f'Tenant assigned: {tenant.name}')
