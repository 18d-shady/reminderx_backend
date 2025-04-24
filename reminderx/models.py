from django.db import models
from django.contrib.auth.models import User

class SubscriptionPlan(models.Model):
    PLAN_CHOICES = [
        ('free', 'Free'),
        ('premium', 'Premium'),
        ('enterprise', 'Enterprise'),
    ]
    
    name = models.CharField(max_length=20, choices=PLAN_CHOICES, unique=True)
    max_particulars = models.IntegerField()
    max_reminders_per_particular = models.IntegerField()
    allow_recurring = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    reminder_time = models.IntegerField(default=3)  # Days before expiration to send a reminder
    subscription_plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile for {self.user.username}"


class Particular(models.Model):
    CATEGORY_CHOICES = [
        ('license', 'Driver’s License'),
        ('passport', 'Passport'),
        ('insurance', 'Insurance'),
        ('subscription', 'Subscription'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='particulars')
    title = models.CharField(max_length=255)
    document = models.FileField(upload_to='documents/', null=True, blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='other')
    expiry_date = models.DateField(null=False)
    notes = models.TextField(blank=True)
    reminded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'title')  # Ensures no duplicate title for same user

    def __str__(self):
        return f"{self.title} - {self.expiry_date}"


class Reminder(models.Model):
    REMINDER_METHOD_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
    ]
    RECURRENCE_CHOICES = [
        ('none', 'None'),
        ('daily', 'Daily'),
        ('every_2_days', 'Every 2 Days'),
    ]
    
    particular = models.ForeignKey(Particular, on_delete=models.CASCADE, related_name='reminders')
    scheduled_date = models.DateTimeField()
    sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    reminder_method = models.CharField(max_length=10, choices=REMINDER_METHOD_CHOICES, default='email')
    reminder_message = models.TextField(blank=True, null=True)
    recurrence = models.CharField(max_length=20, choices=RECURRENCE_CHOICES, default='none')
    start_days_before = models.IntegerField(default=3)  # How many days before expiry to start


    def __str__(self):
        return f"Reminder for {self.particular.title} on {self.scheduled_date}"
    


