import logging

from django.apps import AppConfig
from decouple import config

logger = logging.getLogger(__name__)


class GovConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gov'

    def ready(self):
        # NGSign needs a partner JWT, but a missing var must NOT take down the
        # whole app at boot (it crashed every management command + gunicorn on
        # prod). NGSign is configured per-tenant via NGSignClientAccount and the
        # integration can be paused; warn instead of raising.
        if not config('NGSIGNE_API', default=''):
            logger.warning(
                'NGSIGNE_API is not set — NGSign signing will be unavailable '
                'until it is configured.'
            )
