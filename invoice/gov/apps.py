import os
from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured


class GovConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gov'

    def ready(self):
        if not os.environ.get('NGSIGNE_API'):
            raise ImproperlyConfigured(
                "NGSIGNE_API environment variable is required for NGSign integration. "
                "Add it to your .env file."
            )
