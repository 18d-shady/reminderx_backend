from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Particular, Reminder, Profile, Notification
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class ProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    profile_picture = serializers.ImageField(required=False, allow_null=True)
    profile_picture_url = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [ 'user', 'phone_number', 'whatsapp_notifications', 'push_notifications', 'email_notifications', 'sms_notifications', 'reminder_time', 'subscription_plan', 'profile_picture', 'profile_picture_url']

    def get_profile_picture_url(self, obj):
        request = self.context.get('request')
        if obj.profile_picture and request:
            return request.build_absolute_uri(obj.profile_picture.url)
        return None

    # def resize_image(self, image_field):
    #     image = Image.open(image_field)
    #     if image.width > 512:
    #         ratio = 512 / float(image.width)
    #         height = int((float(image.height) * float(ratio)))
    #         image = image.resize((512, height), Image.LANCZOS)
    #         buffer = BytesIO()
    #         image_format = image_field.name.split('.')[-1].upper()
    #         if image_format == 'JPG':
    #             image_format = 'JPEG'
    #         image.save(buffer, format=image_format)
    #         return ContentFile(buffer.getvalue(), name=image_field.name)
    #     return image_field

    def update(self, instance, validated_data):
        profile_picture = validated_data.get('profile_picture', None)
        # if profile_picture:
        #     validated_data['profile_picture'] = self.resize_image(profile_picture)
        return super().update(instance, validated_data)

    def create(self, validated_data):
        profile_picture = validated_data.get('profile_picture', None)
        # if profile_picture:
        #     validated_data['profile_picture'] = self.resize_image(profile_picture)
        return super().create(validated_data)


class ReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reminder
        fields = '__all__'
        read_only_fields = ['sent', 'sent_at']

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'

class ParticularSerializer(serializers.ModelSerializer):
    document_url = serializers.SerializerMethodField()
    reminders = ReminderSerializer(many=True, read_only=True)

    class Meta:
        model = Particular
        fields = '__all__'
        read_only_fields = ['user', 'created_at', 'reminded']

    def get_document_url(self, obj):
        request = self.context.get('request')
        if obj.document and request:
            return request.build_absolute_uri(obj.document.url)
        return None

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={"input_type": "password"})
    email = serializers.EmailField(required=True)
    username = serializers.CharField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password')
        extra_kwargs = {
            'username': {'required': True},
            'email': {'required': True}
        }

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already in use.")
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already taken.")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"]
        )
        return user


#adding this for login with both username and email
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        login = attrs.get("username")
        password = attrs.get("password")

        user = User.objects.filter(username=login).first()
        if user is None:
            user = User.objects.filter(email=login).first()

        if user is None or not user.check_password(password):
            raise serializers.ValidationError("Invalid credentials")

        attrs['username'] = user.username  # Ensure correct username is passed
        data = super().validate(attrs)

        return data
