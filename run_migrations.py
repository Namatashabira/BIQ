import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'admin_panel.settings')
django.setup()

from django.core.management import call_command

print("Creating migrations...")
call_command('makemigrations', 'core')
print("\nApplying migrations...")
call_command('migrate')
print("\nDone!")
