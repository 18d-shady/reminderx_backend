from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile, SubscriptionPlan
from django.db.utils import OperationalError, ProgrammingError
from django.db import connection
from django_rest_passwordreset.signals import reset_password_token_created
from django.core.mail import send_mail
from django.conf import settings
import os
import requests


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
    # Check if the table exists
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'reminderx_subscriptionplan'
                );
            """)
            table_exists = cursor.fetchone()[0]
    except Exception:
        table_exists = False

    if not table_exists:
        return

    plans = [
        {"name": "free", "max_particulars": 9999, "max_reminders_per_particular": 9999, "allow_recurring": True},
        {"name": "premium", "max_particulars": 9999, "max_reminders_per_particular": 9999, "allow_recurring": True},
        {"name": "enterprise", "max_particulars": 9999, "max_reminders_per_particular": 9999, "allow_recurring": True},
    ]
    for plan in plans:
        try:
            SubscriptionPlan.objects.get_or_create(name=plan["name"], defaults=plan)
        except Exception:
            pass


@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance, reset_password_token, *args, **kwargs):
    requests.post(
  		"https://api.mailgun.net/v3/naikas.com/messages",
        auth=("api", os.environ.get('MAILGUN_API')),
        data={"from": "Naikas <postmaster@naikas.com>",
			"to": [reset_password_token.user.email],
  			"subject": "Password Reset for Naikas",
  			"text": f"Use this token to reset your password: {reset_password_token.key}"}
    )
    """
    send_mail(
        subject="Password Reset for Naikas",
        message=f"Use this token to reset your password: {reset_password_token.key}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[reset_password_token.user.email],
    )
    """
    
def send_simple_message():
  	return 

