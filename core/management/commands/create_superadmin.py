from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Create a superadmin user for the multi-tenant system'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Superadmin email')
        parser.add_argument('--password', type=str, help='Superadmin password')

    def handle(self, *args, **options):
        email = options.get('email') or 'superadmin@example.com'
        password = options.get('password') or 'superadmin123'
        
        if User.objects.filter(email=email).exists():
            self.stdout.write(
                self.style.WARNING(f'User with email {email} already exists')
            )
            return
        
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            role='superadmin',
            is_staff=True,
            is_superuser=True
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created superadmin user: {email}')
        )
        self.stdout.write(f'Password: {password}')