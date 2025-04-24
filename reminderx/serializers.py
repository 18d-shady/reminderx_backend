from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Particular, Reminder


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'email']


class ParticularSerializer(serializers.ModelSerializer):
    class Meta:
        model = Particular
        fields = '__all__'
        read_only_fields = ['user', 'created_at', 'reminded']


class ReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reminder
        fields = '__all__'
        read_only_fields = ['sent', 'sent_at']

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ('username', 'email', 'password')

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already in use.")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"]
        )
        return user
