import os
import firebase_admin
from firebase_admin import messaging, credentials
from twilio.rest import Client
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from reminderx.models import Notification, Profile

# Firebase init
cred_path = os.path.join(os.path.dirname(__file__), '../../../firebase_credentials.json')
if not firebase_admin._apps:
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)

# Twilio init
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# SendGrid setup (optional)
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
USE_SENDGRID = bool(SENDGRID_API_KEY)

class Command(BaseCommand):
    help = "Send unsent notifications"

    def handle(self, *args, **kwargs):
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        notifications = Notification.objects.filter(sent=False)

        for n in notifications:
            profile = Profile.objects.get(user=n.user)
            all_success = True

            # Email
            if n.send_email and n.user.email:
                try:
                    if USE_SENDGRID:
                        sg_message = Mail(
                            from_email='noreply@reminderx.com',
                            to_emails=n.user.email,
                            subject=f"Reminder: {n.particular_title}",
                            plain_text_content=n.message,
                            html_content=f"<p>{n.message}</p>",
                        )
                        sg = SendGridAPIClient(SENDGRID_API_KEY)
                        response = sg.send(sg_message)
                        self.stdout.write(f"✅ SendGrid email sent to {n.user.email} (status: {response.status_code})")
                    else:
                        send_mail(
                            subject=f"Reminder: {n.particular_title}",
                            message=n.message,
                            from_email='noreply@reminderx.com',
                            recipient_list=[n.user.email],
                            fail_silently=False,
                        )
                        self.stdout.write(f"✅ Email sent to {n.user.email}")
                except Exception as e:
                    self.stdout.write(f"❌ Email failed: {e}")
                    all_success = False

            # SMS
            if n.send_sms and profile.phone_number:
                try:
                    client.messages.create(
                        body=n.message,
                        from_=TWILIO_PHONE_NUMBER,
                        to=profile.phone_number
                    )
                    self.stdout.write(f"✅ SMS sent to {profile.phone_number}")
                except Exception as e:
                    self.stdout.write(f"❌ SMS failed: {e}")
                    all_success = False

            # WhatsApp
            if n.send_whatsapp and profile.phone_number:
                try:
                    client.messages.create(
                        body=n.message,
                        from_='whatsapp:' + TWILIO_PHONE_NUMBER,
                        to='whatsapp:' + profile.phone_number
                    )
                    self.stdout.write(f"✅ WhatsApp sent to {profile.phone_number}")
                except Exception as e:
                    self.stdout.write(f"❌ WhatsApp failed: {e}")
                    all_success = False

            # Push Notification
            if n.send_push:
                try:
                    fcm_token = getattr(profile, "fcm_token", None)
                    if fcm_token:
                        messaging.send(messaging.Message(
                            token=fcm_token,
                            notification=messaging.Notification(
                                title="ReminderX",
                                body=n.message,
                            )
                        ))
                        self.stdout.write(f"✅ Push notification sent to {n.user.username}")
                except Exception as e:
                    self.stdout.write(f"❌ Push failed: {e}")
                    all_success = False

            # Mark as sent
            if all_success:
                n.sent = True
                n.save()
