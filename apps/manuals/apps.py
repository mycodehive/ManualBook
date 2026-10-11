from django.apps import AppConfig


class ManualsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.manuals'

    def ready(self):
        from apps.organizations.public_access import register_public_reader
        from .public_access import public_reader_for
        register_public_reader(public_reader_for)
