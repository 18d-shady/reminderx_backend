from rest_framework import permissions
from .models import Particular, Reminder

class CanCreateParticular(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        profile = user.profile
        max_allowed = profile.subscription_plan.max_particulars
        current_count = user.particulars.count()
        return current_count < max_allowed

class CanCreateReminder(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        profile = user.profile
        data = request.data

        # Only check on POST
        if request.method != 'POST':
            return True

        particular_id = data.get("particular")
        if not particular_id:
            return False

        try:
            particular = Particular.objects.get(id=particular_id, user=user)
        except Particular.DoesNotExist:
            return False

        existing_reminders = particular.reminders.count()
        max_reminders = profile.subscription_plan.max_reminders_per_particular

        # Disallow if exceeding reminder limit
        if existing_reminders >= max_reminders:
            return False

        # If recurring not allowed
        if not profile.subscription_plan.allow_recurring:
            is_recurring = data.get("is_recurring", False)
            if is_recurring:
                return False

        return True
