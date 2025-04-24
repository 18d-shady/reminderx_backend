from django.apps import AppConfig
from django.db.utils import OperationalError, ProgrammingError

class ReminderxConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reminderx'

    def ready(self):
        import reminderx.signals  # Keep your signal import
        
        # Import here to avoid circular import issues
        from .models import SubscriptionPlan

        try:
            # Check and create subscription plans if they don't exist
            plans = [
                {"name": "free", "max_particulars": 5, "max_reminders_per_particular": 2, "allow_recurring": False},
                {"name": "premium", "max_particulars": 20, "max_reminders_per_particular": 10, "allow_recurring": True},
                {"name": "enterprise", "max_particulars": 9999, "max_reminders_per_particular": 9999, "allow_recurring": True},
            ]
            for plan in plans:
                SubscriptionPlan.objects.get_or_create(name=plan["name"], defaults=plan)

        except (OperationalError, ProgrammingError):
            # Skip this if database isn't ready (e.g. during first migrate)
            pass
