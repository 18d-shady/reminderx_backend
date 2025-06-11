from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile, SubscriptionPlan
from django.db.utils import OperationalError, ProgrammingError

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        try:
            default_plan = SubscriptionPlan.objects.get(name="free")
        except (SubscriptionPlan.DoesNotExist, OperationalError, ProgrammingError):
            default_plan = None 

        Profile.objects.create(user=instance, subscription_plan=default_plan)
    else:
        # Update existing profile (if it exists)
        if hasattr(instance, "profile"):
            instance.profile.save()

@receiver(post_migrate)
def create_subscription_plans(sender, **kwargs):
    plans = [
        {"name": "free", "max_particulars": 9999, "max_reminders_per_particular": 9999, "allow_recurring": True},
        {"name": "premium", "max_particulars": 9999, "max_reminders_per_particular": 9999, "allow_recurring": True},
        {"name": "enterprise", "max_particulars": 9999, "max_reminders_per_particular": 9999, "allow_recurring": True},
    ]
    for plan in plans:
        SubscriptionPlan.objects.get_or_create(name=plan["name"], defaults=plan)
