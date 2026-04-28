"""
WSGI config for admin_panel project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""
import sys
import os

if os.name == 'nt':
    # Windows only: force UTF-8 console
    os.environ['PYTHONUTF8'] = '1'
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')


import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'admin_panel.settings')

application = get_wsgi_application()
