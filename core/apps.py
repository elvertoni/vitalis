from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Núcleo'

    def ready(self):
        from .signals import connect_file_cleanup

        connect_file_cleanup()
