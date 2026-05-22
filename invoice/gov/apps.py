from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured
from decouple import config, UndefinedValueError


class GovConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gov'

    def ready(self):
        try:
            config('NGSIGNE_API')
        except UndefinedValueError:
            raise ImproperlyConfigured(
                "NGSIGNE_API environment variable is required for NGSign integration. "
                "Add it to your .env file."
            )
