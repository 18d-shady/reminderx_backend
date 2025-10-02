from django.shortcuts import render
import requests
import random
from rest_framework import generics, permissions, status
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import RetrieveUpdateAPIView
from django.core.mail import send_mail
from .permissions import CanCreateParticular, CanCreateReminder
from .models import Organization, Particular, Reminder, Notification, get_allowed_methods, EmailVerification, SubscriptionPlan, Profile
from .serializers import (
    OrganizationDetailSerializer,
    ParticularSerializer,
    ReminderSerializer,
    RegisterSerializer,
    ProfileSerializer,
    NotificationSerializer,
    CustomTokenObtainPairSerializer,
    BulkParticularListSerializer,
    OrganizationCreateSerializer
)
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import ValidationError
from django.conf import settings
import os
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.shortcuts import get_object_or_404
from django.db.models import Q
from twilio.rest import Client
from .utils import initialize_transaction, verify_transaction


TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def current_user_view(request):
    profile = request.user.profile
    if request.method == 'GET':
        serializer = ProfileSerializer(profile, context={'request': request})
        return Response(serializer.data)
    elif request.method in ['PUT', 'PATCH']:
        serializer = ProfileSerializer(profile, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    elif request.method == 'DELETE':
        try:
            # Delete the user (this will cascade delete the profile due to CASCADE in Profile model)
            request.user.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# Create or list user's particulars
class ParticularListCreateView(generics.ListCreateAPIView):
    serializer_class = ParticularSerializer
    permission_classes = [permissions.IsAuthenticated & CanCreateParticular]

    def get_queryset(self):
        #return self.request.user.particulars.all()
        user = self.request.user
        return Particular.objects.filter(
            Q(user=user) | Q(owners=user.profile)  # include owner-linked particulars
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# GET (retrieve) and PUT/PATCH (update) particular
class ParticularDetailUpdateView(RetrieveUpdateAPIView):
    serializer_class = ParticularSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Particular.objects.filter(
            Q(user=user) | Q(owners=user.profile)
        ).distinct()

    def delete(self, request, *args, **kwargs):
        particular = self.get_object()
        # Delete will cascade to reminders due to CASCADE in model
        particular.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# Search user's particulars by title
class ParticularSearchView(generics.ListAPIView):
    serializer_class = ParticularSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        user_particulars = self.request.user.particulars.all()
        search_query = self.request.query_params.get('q', None)
        if search_query:
            return user_particulars.filter(title__icontains=search_query)
        return user_particulars
        """
        user = self.request.user
        queryset = Particular.objects.filter(
            Q(user=user) | Q(owners=user.profile)
        ).distinct()

        search_query = self.request.query_params.get('q')
        if search_query:
            queryset = queryset.filter(title__icontains=search_query)
        return queryset


# Create or list reminders
class ReminderListCreateView(generics.ListCreateAPIView):
    serializer_class = ReminderSerializer
    permission_classes = [permissions.IsAuthenticated & CanCreateReminder]

    def get_queryset(self):
        #return Reminder.objects.filter(particular__user=self.request.user)
        user = self.request.user
        return Reminder.objects.filter(
            Q(particular__user=user) | Q(particular__owners=user.profile)
        ).distinct()

    def perform_create(self, serializer):
        particular = serializer.validated_data['particular']
        user = self.request.user

        if not (particular.user == user or user.profile in particular.owners.all()):
            raise ValidationError("Unauthorized")

        profile = self.request.user.profile
        allowed_methods = get_allowed_methods(profile)
        requested_methods = serializer.validated_data.get('reminder_methods', [])

        invalid = [method for method in requested_methods if method not in allowed_methods]
        if invalid:
            raise ValidationError(f"Invalid reminder methods for your plan: {invalid}")

        serializer.save()



# GET and PUT/PATCH for individual reminder
class ReminderUpdateView(RetrieveUpdateAPIView):
    serializer_class = ReminderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Reminder.objects.filter(
            Q(particular__user=user) | Q(particular__owners=user.profile)
        ).distinct()

class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')

# Register new user and return JWT tokens
class RegisterView(APIView):
    def post(self, request):
        otp = request.data.get("otp")
        email = request.data.get("email")
        # Require OTP for registration
        if not otp or not email:
            return Response({"error": "OTP and email are required for registration."}, status=400)
        record = EmailVerification.objects.filter(email=email, otp=otp).last()
        if not record or record.is_expired():
            return Response({"error": "Invalid or expired OTP. Please verify your email first."}, status=400)
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = serializer.save()
                refresh = RefreshToken.for_user(user)
                # Clean up OTP record after successful registration
                record.delete()
                return Response({
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response({
                    "error": "Failed to create user",
                    "detail": str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({
            "error": "Validation failed",
            "details": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

class SendVerificationEmail(APIView):
    def post(self, request):
        email = request.data.get("email")
        username = request.data.get("username")
        if not email:
            return Response({"error": "Email is required"}, status=400)
        if not username:
            return Response({"error": "Username is required"}, status=400)

        if User.objects.filter(email=email).exists():
            return Response({"error": "Email already in use."}, status=400)
        if User.objects.filter(username=username).exists():
            return Response({"error": "Username already taken."}, status=400)

        otp = str(random.randint(100000, 999999))
        EmailVerification.objects.create(email=email, otp=otp)
        """
        send_mail(
            subject="Naikas OTP Code",
            message=f"Your OTP code is {otp}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        """
        requests.post(
            "https://api.mailgun.net/v3/naikas.com/messages",
            auth=("api", os.environ.get('MAILGUN_API')),
            data={"from": "Naikas <postmaster@naikas.com>",
                "to": [email],
                "subject": "Naikas OTP Code",
                "text": f"Your OTP code is {otp}"}
        )
        

        return Response({"message": "OTP sent"}, status=200)

class RegisterFCMTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get("token")
        platform = request.data.get("platform")  # 'web', 'android', 'ios'

        if not token or not platform:
            return Response({"error": "Token and platform are required."}, status=status.HTTP_400_BAD_REQUEST)

        profile = request.user.profile

        if platform == "web":
            profile.fcm_web_token = token
        elif platform == "android":
            profile.fcm_android_token = token
        elif platform == "ios":
            profile.fcm_ios_token = token
        else:
            return Response({"error": "Invalid platform."}, status=status.HTTP_400_BAD_REQUEST)

        profile.save()
        return Response({"message": "Token saved successfully."})


class BulkParticularCreateView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = BulkParticularListSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            created_docs = serializer.save()
            return Response(
                {
                    "message": f"{len(created_docs)} documents (with reminders) created successfully.",
                    "particulars": [p.id for p in created_docs]
                },
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    
@api_view(["POST"])
def manual_upgrade(request):
    plan_name = request.data.get("plan")
    if not plan_name:
        return Response({"error": "plan is required"}, status=400)

    try:
        plan = SubscriptionPlan.objects.get(name=plan_name)
    except SubscriptionPlan.DoesNotExist:
        return Response({"error": f"Plan '{plan_name}' does not exist"}, status=404)

    profile = request.user.profile
    profile.subscription_plan = plan
    profile.save()

    return Response({"status": "success", "new_plan": plan.name})

class CreateOrganizationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OrganizationCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            organization = serializer.save()
            return Response({
                "id": organization.id,
                "organizational_id": organization.organizational_id,
                "name": organization.name
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class VerifyOrganizationView(APIView):
    """
    Simple endpoint to verify if an organization exists by organizational_id.
    """
    def get(self, request, *args, **kwargs):
        org_id = request.query_params.get("org_id")

        if not org_id:
            return Response({"detail": "organizational_id is required."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            org = Organization.objects.get(organizational_id=org_id)
            return Response({
                "exists": True,
                "id": org.id,
                "name": org.name,
                "organizational_id": org.organizational_id,
                "admin": {
                    "id": org.admin.id,
                    "username": org.admin.user.username,
                    "email": org.admin.user.email,
                }
            }, status=status.HTTP_200_OK)

        except Organization.DoesNotExist:
            return Response({"exists": False}, status=status.HTTP_404_NOT_FOUND)


class VerifyStaffView(APIView):
    permission_classes = [IsAuthenticated]  # Admin must be logged in

    def post(self, request):
        token = request.data.get("token")
        if not token:
            return Response({"error": "Token is required."}, status=400)

        signer = TimestampSigner()
        try:
            profile_id = signer.unsign(token, max_age=60*60*24)  # 24h expiry
        except SignatureExpired:
            return Response({"error": "Verification link expired."}, status=400)
        except BadSignature:
            return Response({"error": "Invalid verification token."}, status=400)

        staff_profile = get_object_or_404(Profile, id=profile_id)

        # ✅ Ensure staff has an organization
        if not staff_profile.organization:
            return Response({"error": "This staff is not linked to any organization."}, status=400)

        # ✅ Ensure staff org matches admin org
        if staff_profile.organization != request.user.profile.organization:
            return Response({"error": "Staff does not belong to your organization."}, status=403)

        # ✅ Ensure the logged-in user is the admin of that org
        if staff_profile.organization.admin != request.user.profile:
            return Response({"error": "You are not authorized to verify this staff."}, status=403)

        # Approve staff
        staff_profile.role = "staff"
        staff_profile.save()

        return Response({"message": f"{staff_profile.user.username} has been verified."}, status=200)


class OrganizationDetailView(generics.RetrieveAPIView):
    queryset = Organization.objects.all()
    serializer_class = OrganizationDetailSerializer
    lookup_field = "organizational_id"


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def manage_particular_owner(request, particular_id):
    """
    POST   -> add owner
    DELETE -> remove owner
    """
    profile = request.user.profile
    particular = get_object_or_404(Particular, id=particular_id)

    # ✅ Must belong to an organization + be admin
    if not profile.organization or profile.organization.admin != profile:
        return Response({"error": "Only organization admin can manage owners."}, status=403)

    target_profile_id = request.data.get("profile_id")
    if not target_profile_id:
        return Response({"error": "profile_id is required."}, status=400)

    target_profile = get_object_or_404(Profile, id=target_profile_id)

    # ✅ Ensure target is in same organization
    if target_profile.organization != profile.organization:
        return Response({"error": "Profile does not belong to your organization."}, status=403)

    if request.method == "POST":
        particular.owners.add(target_profile)
        return Response({
            "status": "assigned",
            "particular_id": particular.id,
            "profile_id": target_profile.id,
            "message": f"{target_profile.user.username} assigned to {particular.title}."
        }, status=200)

    elif request.method == "DELETE":
        if target_profile == particular.user.profile:
            return Response({"error": "Cannot remove the document creator."}, status=400)

        particular.owners.remove(target_profile)
        return Response({
            "status": "removed",
            "particular_id": particular.id,
            "profile_id": target_profile.id,
            "message": f"{target_profile.user.username} removed from {particular.title}."
        }, status=200)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def staff_particulars_view(request, profile_id):
    """
    Admin-only endpoint: fetch all particulars created by or owned by a staff member.
    """
    admin_profile = request.user.profile
    staff_profile = get_object_or_404(Profile, id=profile_id)

    # ✅ Must belong to an organization + be admin
    if not admin_profile.organization or admin_profile.organization.admin != admin_profile:
        return Response({"error": "Only organization admin can view staff particulars."}, status=403)

    if staff_profile.organization != admin_profile.organization:
        return Response({"error": "Staff does not belong to your organization."}, status=403)

    # ✅ Fetch created + owned particulars
    created = Particular.objects.filter(user=staff_profile.user)
    owned = Particular.objects.filter(owners=staff_profile)

    data = {
        "staff": {
            "id": staff_profile.id,
            "username": staff_profile.user.username,
            "email": staff_profile.user.email,
        },
        "created_particulars": [
            {"id": p.id, "title": p.title, "expiry_date": p.expiry_date}
            for p in created
        ],
        "owned_particulars": [
            {"id": p.id, "title": p.title, "expiry_date": p.expiry_date}
            for p in owned
        ],
    }
    return Response(data, status=200)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def send_message_view(request, profile_id):

    admin_profile = request.user.profile
    staff_profile = get_object_or_404(Profile, id=profile_id)

    if not admin_profile.organization or admin_profile.organization.admin != admin_profile:
        return Response({"error": "Only organization admin can send messages."}, status=403)

    # ✅ ensure same organization
    if staff_profile.organization != admin_profile.organization:
        return Response({"error": "Staff not in your organization."}, status=403)

    channel = request.data.get("channel")  # "sms" or "whatsapp"
    message = request.data.get("message")

    if not message:
        return Response({"error": "Message is required"}, status=400)
    if not staff_profile.phone_number:
        return Response({"error": "Staff has no phone number"}, status=400)

    try:
        if channel == "sms":
            client.messages.create(
                body=message,
                from_=TWILIO_PHONE_NUMBER,
                to=staff_profile.phone_number
            )
            return Response({"success": f"SMS sent to {staff_profile.phone_number}"})

        elif channel == "whatsapp":
            client.messages.create(
                body=message,
                from_="whatsapp:" + TWILIO_PHONE_NUMBER,
                to="whatsapp:" + staff_profile.phone_number
            )
            return Response({"success": f"WhatsApp sent to {staff_profile.phone_number}"})

        else:
            return Response({"error": "Invalid channel. Use 'sms' or 'whatsapp'."}, status=400)

    except Exception as e:
        return Response({"error": str(e)}, status=500)
    
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_staff_view(request, profile_id):
    """
    Admin-only endpoint: delete a staff user under the same organization.
    """
    admin_profile = request.user.profile
    staff_profile = get_object_or_404(Profile, id=profile_id)

    # ✅ Ensure caller is an organization admin
    if not admin_profile.organization or admin_profile.organization.admin != admin_profile:
        return Response({"error": "Only organization admin can delete staff."}, status=403)

    # ✅ Ensure staff is in the same organization
    if staff_profile.organization != admin_profile.organization:
        return Response({"error": "Staff does not belong to your organization."}, status=403)

    # ✅ Prevent deleting the admin themselves
    if staff_profile == admin_profile:
        return Response({"error": "Admin cannot delete themselves."}, status=400)

    # ✅ Delete user (cascade deletes profile too)
    staff_profile.user.delete()

    return Response(
        {"message": f"User {staff_profile.user.username} deleted successfully."},
        status=200
    )

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def set_organization_icon(request, org_id):
    profile = request.user.profile
    org = get_object_or_404(Organization, organizational_id=org_id)

    # ✅ Only admin can update
    if org.admin != profile:
        return Response({"error": "Only the admin can update organization icon."}, status=403)

    file = request.FILES.get("icon")
    if not file:
        return Response({"error": "Icon file is required."}, status=400)

    org.icon = file
    org.save()

    return Response({
        "message": "Organization icon updated successfully.",
        "icon_url": request.build_absolute_uri(org.icon.url)
    })

PLAN_AMOUNTS = {
    "premium": 150000,     # ₦1500.00 in kobo
    "enterprise": 5000000, # ₦50000.00 in kobo
    "multiusers": 10000000, # ₦100000.00 in kobo
}

class PaystackInitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        email = request.data.get("email")
        plan = request.data.get("plan")
        callback_url = request.data.get("callback_url")

        amount = PLAN_AMOUNTS.get(plan)
        if not amount:
            return Response({"status": False, "message": "Invalid plan"}, status=400)

        result = initialize_transaction(email, amount, callback_url, plan, request.user.id)
        return Response(result)

from datetime import timedelta
from django.utils.timezone import now

class PaystackVerifyView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, reference):
        result = verify_transaction(reference)

        if not result.get("status"):
            return Response({"error": "Verification failed"}, status=400)

        data = result.get("data", {})
        if data.get("status") != "success":
            return Response({"error": "Transaction not successful"}, status=400)

        plan = data.get("metadata", {}).get("plan")
        amount_paid = data.get("amount", 0)  # in kobo

        monthly_price = PLAN_AMOUNTS.get(plan)
        if not monthly_price:
            return Response({"error": "Unknown plan"}, status=400)

        months_paid = amount_paid // monthly_price
        if months_paid < 1:
            return Response({"error": "Amount too low for selected plan"}, status=400)

        # Upgrade user profile
        profile = request.user.profile
        try:
            plan_obj = SubscriptionPlan.objects.get(name=plan)
        except SubscriptionPlan.DoesNotExist:
            return Response({"error": f"Plan {plan} not found"}, status=404)

        profile.subscription_plan = plan_obj

        # Calculate new expiry date
        if profile.subscription_expiry and profile.subscription_expiry > now():
            # extend current expiry
            profile.subscription_expiry += timedelta(days=30 * months_paid)
        else:
            # start new subscription
            profile.subscription_expiry = now() + timedelta(days=30 * months_paid)

        profile.save()

        return Response({
            "status": "success",
            "plan": plan,
            "months_added": months_paid,
            "new_expiry": profile.subscription_expiry,
        })
