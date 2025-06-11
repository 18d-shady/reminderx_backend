from django.shortcuts import render

from rest_framework import generics, permissions, status
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import RetrieveUpdateAPIView
from .permissions import CanCreateParticular, CanCreateReminder
from .models import Particular, Reminder, Notification, get_allowed_methods
from .serializers import (
    ParticularSerializer,
    ReminderSerializer,
    RegisterSerializer,
    ProfileSerializer,
    NotificationSerializer,
)
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import ValidationError


@api_view(['GET', 'PUT', 'PATCH'])
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
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = serializer.save()
                refresh = RefreshToken.for_user(user)
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
