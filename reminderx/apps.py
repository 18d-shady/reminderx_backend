from django.apps import AppConfig

class ReminderxConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reminderx'

    def ready(self):
        import reminderx.signals  # Signal registration only
