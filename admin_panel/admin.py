from django.contrib import admin
from django.apps import apps

# Loop through all installed apps
for app_config in apps.get_app_configs():
    # Skip built-in Django apps if you want (optional)
    if app_config.name.startswith("django."):
        continue

    # Loop through all models in the app
    for model_name, model in app_config.models.items():
        try:
            admin.site.register(model)
        except admin.sites.AlreadyRegistered:
            pass  # Ignore if already registered
