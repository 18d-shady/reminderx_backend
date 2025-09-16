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
        return self.request.user.particulars.all()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# GET (retrieve) and PUT/PATCH (update) particular
class ParticularDetailUpdateView(RetrieveUpdateAPIView):
    serializer_class = ParticularSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Particular.objects.filter(user=self.request.user)

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
        user_particulars = self.request.user.particulars.all()
        search_query = self.request.query_params.get('q', None)
        if search_query:
            return user_particulars.filter(title__icontains=search_query)
        return user_particulars


# Create or list reminders
class ReminderListCreateView(generics.ListCreateAPIView):
    serializer_class = ReminderSerializer
    permission_classes = [permissions.IsAuthenticated & CanCreateReminder]

    def get_queryset(self):
        return Reminder.objects.filter(particular__user=self.request.user)

    def perform_create(self, serializer):
        particular = serializer.validated_data['particular']
        if particular.user != self.request.user:
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
        return Reminder.objects.filter(particular__user=self.request.user)

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
