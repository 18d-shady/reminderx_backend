from rest_framework import permissions
from .models import Particular, Reminder
from rest_framework.exceptions import PermissionDenied


class CanCreateParticular(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method not in permissions.SAFE_METHODS:  # Only POST, PUT, etc.
            user = request.user
            profile = user.profile
            max_allowed = profile.subscription_plan.max_particulars

            # No plan assigned
            if max_allowed is None:
                return True  # Unlimited

            # Sentinel -1 also means unlimited
            if max_allowed == -1:
                return True

            current_count = user.particulars.count()
            if current_count >= max_allowed:
                raise PermissionDenied(
                    f"You have reached your plan's limit of {max_allowed} reminders."
                )
            return True
        return True  # Allow safe methods like GET

"""
class CanCreateParticular(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method not in permissions.SAFE_METHODS:  # Only apply on POST, PUT, etc.
            user = request.user
            profile = user.profile
            max_allowed = profile.subscription_plan.max_particulars
            if not max_allowed:
                raise PermissionDenied("No subscription plan assigned to your profile.")
            current_count = user.particulars.count()
            return current_count < max_allowed
        return True  # Allow safe methods like GET
"""

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
