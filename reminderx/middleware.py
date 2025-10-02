from django.utils.timezone import now
from .models import SubscriptionPlan

class SubscriptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            profile = getattr(request.user, "profile", None)
            if profile and profile.subscription_expiry:
                if profile.subscription_expiry < now():
                    # Downgrade to Free
                    try:
                        free_plan = SubscriptionPlan.objects.get(name="free")
                        profile.subscription_plan = free_plan
                        profile.subscription_expiry = None
                        profile.save()
                    except SubscriptionPlan.DoesNotExist:
                        pass

        return self.get_response(request)
