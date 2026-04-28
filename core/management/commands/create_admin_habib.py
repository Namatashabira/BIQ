from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from accounts.models import ROLE_SUPERADMIN


User = get_user_model()

class Command(BaseCommand):
    help = "Create admin user Habib"

    def handle(self, *args, **options):
        username = "Habib"
        password = "1Habib@25"
        email = "habib@admin.com"
        
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f"User '{username}' already exists"))
            return
            
        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            role=ROLE_SUPERADMIN
        )
        
        self.stdout.write(self.style.SUCCESS(f"Successfully created admin user '{username}'"))