from django.apps import AppConfig


class AppointmentsConfig(AppConfig):
    name = 'appointments'

    def ready(self):
        from . import signals  # noqa: F401
