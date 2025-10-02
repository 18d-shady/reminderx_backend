import os
from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone
from datetime import timedelta
import random

def user_directory_path(instance, filename):
    # If this is a profile picture
    if hasattr(instance, 'user') and isinstance(instance, Profile):
        ext = filename.split('.')[-1]
        return f'user_{instance.user.id}/profile_picture.{ext}'
    
    # For Particular documents
    ext = filename.split('.')[-1]
    safe_title = instance.title.replace(" ", "_").lower()
    return f'user_{instance.user.id}/{safe_title}.{ext}'

def get_free_plan():
    try:
        return SubscriptionPlan.objects.get(name="free").id
    except SubscriptionPlan.DoesNotExist:
        return None


class SubscriptionPlan(models.Model):
    PLAN_CHOICES = [
        ('free', 'Free'),
        ('premium', 'Premium'),
        ('enterprise', 'Enterprise'),
        ('multiusers', 'Multiusers'),
    ]
    
    name = models.CharField(max_length=20, choices=PLAN_CHOICES, unique=True)
    max_particulars = models.IntegerField()
    max_reminders_per_particular = models.IntegerField()
    allows_multi_user = models.BooleanField(default=False) 
    allow_recurring = models.BooleanField(default=False)

    def __str__(self):
        return self.name

def organization_icon_path(instance, filename):
    ext = filename.split('.')[-1]
    return f'organization_{instance.organizational_id}/icon.{ext}'

class Organization(models.Model):
    organizational_id = models.CharField(max_length=6, unique=True)  # 6-digit ID
    name = models.CharField(max_length=255)
    admin = models.ForeignKey(
        'Profile',  # Admin profile
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_organization'
    )
    icon = models.ImageField(upload_to=organization_icon_path, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.organizational_id})"

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    push_notifications = models.BooleanField(default=True)
    whatsapp_notifications = models.BooleanField(default=False)
    reminder_time = models.IntegerField(default=3)
    subscription_plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, default=get_free_plan)
    profile_picture = models.ImageField(upload_to=user_directory_path, null=True, blank=True)
    fcm_web_token = models.CharField(max_length=255, blank=True, null=True)
    fcm_android_token = models.CharField(max_length=255, blank=True, null=True)
    fcm_ios_token = models.CharField(max_length=255, blank=True, null=True)
    subscription_expiry = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members"
    )

    role = models.CharField(
        max_length=20,
        choices=[("admin", "Admin"), ("staff", "Staff"), ("unverified", "Unverified"), ("manager", "Manager")],
        default="admin"
    )

    def save(self, *args, **kwargs):
        # 🔒 Restrict free plan to push notifications only
        if self.subscription_plan and self.subscription_plan.name == "free":
            self.email_notifications = False
            self.sms_notifications = False
            self.whatsapp_notifications = False
            self.push_notifications = True
        super().save(*args, **kwargs)


    def __str__(self):
        return f"Profile for {self.user.username}"
    



class Particular(models.Model):
    CATEGORY_CHOICES = [
        ('vehicle', 'Vehicle'),
        ('travels', 'Travels'),
        ('personal', 'Personal'),
        ('work', 'Work'),
        ('professional', 'Professional'),
        ('household', 'Household'),
        ('finance', 'Finance'),
        ('health', 'Health'),
        ('social', 'Social'),
        ('education', 'Education'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='particulars')
    title = models.CharField(max_length=255)
    document = models.FileField(upload_to=user_directory_path, null=True, blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='other')
    expiry_date = models.DateField(null=False)
    notes = models.TextField(blank=True)
    completed = models.BooleanField(default=False)
    #for multi-user plans
    owners = models.ManyToManyField("Profile", related_name="owned_particulars", blank=True)
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
        ('whatsapp', 'WhatsApp'),
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
    #reminder_method = models.CharField(max_length=10, choices=REMINDER_METHOD_CHOICES, default='email')
    reminder_methods = ArrayField(
        models.CharField(max_length=10, choices=REMINDER_METHOD_CHOICES),
        default=list
    )
    reminder_message = models.TextField(blank=True, null=True)
    recurrence = models.CharField(max_length=20, choices=RECURRENCE_CHOICES, default='none')
    start_days_before = models.IntegerField(default=3)  # How many days before expiry to start


    def __str__(self):
        return f"Reminder for {self.particular.title} on {self.scheduled_date}"

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    particular_title = models.CharField(max_length=255)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    send_email = models.BooleanField(default=False)
    send_sms = models.BooleanField(default=False)
    send_push = models.BooleanField(default=False)
    send_whatsapp = models.BooleanField(default=False)

    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Notification for {self.user.username} - {self.particular_title}"
    

class EmailVerification(models.Model):
    email = models.EmailField()
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=10)
    


def get_allowed_methods(profile: Profile):
    return [
        method for method, enabled in {
            'email': profile.email_notifications,
            'sms': profile.sms_notifications,
            'push': profile.push_notifications,
            'whatsapp': profile.whatsapp_notifications,
        }.items() if enabled
    ]


"""
Vehicle	
	Driver's License
	Vehicle Registration Certificate (VRC)
	Proof of Ownership
	Insurance Certificate
	Roadworthiness Certificate
	Vehicle License
	Hackney Permit
	Oil Change
	Maintenace
Travels	
	Ticket Booking
	Hotel Reservation
	Visa 
	International Passport
	Travel insurance
	Shopping
	Vaccinations
	
Personal	
	Milestones
	Self-Care
	Hobbies & Interests
	Personal Goals
	Donations
	
Work	
	Meetings
	Deadlines
	Communication
	Team Tasks
	Administrative
	Licence expiry
	Permits expiry
	Tax Annual Returns deadlie
	Audit Annual Returns deadlie
	
Professional	
	Membership
	Practice Licence
	Development
	Networking
	Career Planning
	Industry Awareness
	Personal Branding
	
Household	
	Bills & Payments
	Shopping
	Maintenance
	Pet Care
	Organization
Finance	
	Budgeting
	Taxes
	Subscriptions
	Investments
	Debt Management
Health	
	Health Insurance
	Appointments
	Medications
	Fitness
	Mental Health
	Check-Ups
	Nutrition
Social	
	Membership
	Connections
	Events
	Networking
	Gift-Giving
	Community
Education	
	School fees
	Assignments
	Exams
	Courses
	Library
	Extracurriculars
    """
