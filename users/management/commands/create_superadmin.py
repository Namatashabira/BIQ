from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from tenants.models import Tenant

User = get_user_model()

class Command(BaseCommand):
    help = 'Create a superadmin user for the system'

    def handle(self, *args, **options):
        # Check if superadmin already exists
        if User.objects.filter(username='SSEMATAADMIN').exists():
            self.stdout.write(self.style.WARNING('Superadmin user already exists!'))
            return

        # Create superadmin user
        admin_user = User.objects.create_superuser(
            username='SSEMATAADMIN',
            email='admin@businessiq.com',
            password='sabira@25',
            first_name='SSEMATA',
            last_name='SABIRA'
        )

        # Create admin tenant
        admin_tenant = Tenant.objects.create(
            name='Platform Administration',
            admin=admin_user,
            is_verified=True
        )

        # Link user to tenant
        admin_user.tenant = admin_tenant
        admin_user.save(update_fields=['tenant'])

        self.stdout.write(self.style.SUCCESS(
            f'✓ Superadmin user created successfully!\n'
            f'  Username: SSEMATAADMIN\n'
            f'  Name: SSEMATA SABIRA\n'
            f'  Password: sabira@25\n'
            f'  Tenant: Platform Administration'
        ))
