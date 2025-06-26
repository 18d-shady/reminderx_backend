from django.shortcuts import render

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
from .models import Particular, Reminder, Notification, get_allowed_methods, EmailVerification
from .serializers import (
    ParticularSerializer,
    ReminderSerializer,
    RegisterSerializer,
    ProfileSerializer,
    NotificationSerializer,
    CustomTokenObtainPairSerializer,
)
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import ValidationError
from django.conf import settings


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

        send_mail(
            subject="Naikas OTP Code",
            message=f"Your OTP code is {otp}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
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
