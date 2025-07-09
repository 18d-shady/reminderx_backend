from django.core.management.base import BaseCommand 
from django.utils import timezone
from reminderx.models import Reminder, Notification, get_allowed_methods
from datetime import timedelta
from django.db.models import Q

class Command(BaseCommand):
    help = 'Generate notifications for due reminders'

    def handle(self, *args, **kwargs):
        now = timezone.now()
        today = now.date()

        # Get scheduled reminders that are due today and not sent yet
        scheduled_reminders = Reminder.objects.filter(
            scheduled_date__lte=now,
            sent=False
        )

        # Get recurring reminders that should trigger today
        recurring_reminders = Reminder.objects.filter(
            recurrence__in=['daily', 'every_2_days'],
            particular__expiry_date__gt=today  # Not expired
        )

        count = 0

        # Process scheduled reminders
        for reminder in scheduled_reminders:
            user = reminder.particular.user
            profile = user.profile
            allowed_methods = get_allowed_methods(profile)

            # Only include methods allowed by profile
            used_methods = [m for m in reminder.reminder_methods if m in allowed_methods]

            if not used_methods:
                continue  # Skip if no usable methods

            # Use custom message if provided, otherwise use default
            message = reminder.reminder_message or f"Reminder: {reminder.particular.title} is due on {reminder.particular.expiry_date}. Please renew it."

            Notification.objects.create(
                user=user,
                particular_title=reminder.particular.title,
                message=message,
                send_email='email' in used_methods,
                send_sms='sms' in used_methods,
                send_push='push' in used_methods,
                send_whatsapp='whatsapp' in used_methods,
            )

            reminder.sent = True
            reminder.sent_at = now
            reminder.save()

            count += 1

        # Process recurring reminders
        for reminder in recurring_reminders:
            days_until_expiry = (reminder.particular.expiry_date - today).days
            
            # Skip if not within start_days_before window
            if days_until_expiry > reminder.start_days_before:
                continue

            # Skip if not a recurrence day
            if reminder.recurrence == 'daily':
                if days_until_expiry < 0:  # Skip if expired
                    continue
            elif reminder.recurrence == 'every_2_days':
                if days_until_expiry < 0 or days_until_expiry % 2 != 0:  # Skip if expired or not an even day
                    continue

            # Check if a notification was already created for this reminder today
            if Notification.objects.filter(
                user=reminder.particular.user,
                particular_title=reminder.particular.title,
                created_at__date=today
            ).exists():
                continue

            user = reminder.particular.user
            profile = user.profile
            allowed_methods = get_allowed_methods(profile)

            # Only include methods allowed by profile
            used_methods = [m for m in reminder.reminder_methods if m in allowed_methods]

            if not used_methods:
                continue  # Skip if no usable methods

            # Use custom message if provided, otherwise use default
            message = reminder.reminder_message or f"Reminder: {reminder.particular.title} is due on {reminder.particular.expiry_date}. Please renew it."

            Notification.objects.create(
                user=user,
                particular_title=reminder.particular.title,
                message=message,
                send_email='email' in used_methods,
                send_sms='sms' in used_methods,
                send_push='push' in used_methods,
                send_whatsapp='whatsapp' in used_methods,
            )

            count += 1

        self.stdout.write(self.style.SUCCESS(f"{count} notifications generated."))
