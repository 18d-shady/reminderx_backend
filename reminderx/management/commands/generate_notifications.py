from django.core.management.base import BaseCommand 
from django.utils import timezone
from reminderx.models import Reminder, Notification, get_allowed_methods

class Command(BaseCommand):
    help = 'Generate notifications for due reminders'

    def handle(self, *args, **kwargs):
        now = timezone.now()
        due_reminders = Reminder.objects.filter(sent=False, scheduled_date__lte=now)

        count = 0

        for reminder in due_reminders:
            user = reminder.particular.user
            profile = user.profile
            allowed_methods = get_allowed_methods(profile)

            # Only include methods allowed by profile
            used_methods = [m for m in reminder.reminder_methods if m in allowed_methods]

            if not used_methods:
                continue  # Skip if no usable methods

            message = f"Reminder: {reminder.particular.title} is due on {reminder.particular.expiry_date}. Please update it."

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

        self.stdout.write(self.style.SUCCESS(f"{count} notifications generated."))
