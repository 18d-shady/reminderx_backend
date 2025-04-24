from django.shortcuts import render

from rest_framework import generics, permissions, status
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from rest_framework.response import Response
from .permissions import CanCreateParticular, CanCreateReminder
from .models import Particular, Reminder
from .serializers import ParticularSerializer, ReminderSerializer, RegisterSerializer
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.hashers import make_password


# Create or list user's particulars
class ParticularListCreateView(generics.ListCreateAPIView):
    serializer_class = ParticularSerializer
    permission_classes = [permissions.IsAuthenticated & CanCreateParticular]

    def get_queryset(self):
        return self.request.user.particulars.all()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# Create or list reminders
class ReminderListCreateView(generics.ListCreateAPIView):
    serializer_class = ReminderSerializer
    permission_classes = [permissions.IsAuthenticated & CanCreateReminder]

    def get_queryset(self):
        return Reminder.objects.filter(particular__user=self.request.user)

    def perform_create(self, serializer):
        # Enforce that user owns the particular
        if serializer.validated_data['particular'].user != self.request.user:
            raise serializers.ValidationError("Unauthorized")
        serializer.save()

class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)