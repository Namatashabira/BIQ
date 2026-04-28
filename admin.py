from django.contrib import admin
from django.apps import apps

app = apps.get_app_config('core')  # replace 'core' with your app name

for model_name, model in app.models.items():
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass
