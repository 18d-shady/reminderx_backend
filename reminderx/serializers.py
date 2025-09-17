from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Particular, Reminder, Profile, Notification, Organization, SubscriptionPlan
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
from django.core.signing import TimestampSigner
import requests
import os


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class OrganizationSerializer(serializers.ModelSerializer):
    admin = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ['id', 'organizational_id', 'name', 'admin', 'icon_url']

    def get_admin(self, obj):
        if obj.admin:
            return {
                "id": obj.admin.id,
                "username": obj.admin.user.username,
                "email": obj.admin.user.email,
            }
        return None


class ProfileSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)
    user = UserSerializer(read_only=True)
    profile_picture = serializers.ImageField(required=False, allow_null=True)
    profile_picture_url = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [ 'user', 'phone_number', 'whatsapp_notifications', 'push_notifications', 'email_notifications', 'sms_notifications', 'reminder_time', 'subscription_plan', 'profile_picture', 'profile_picture_url',  'organization', 'role']

    def get_profile_picture_url(self, obj):
        request = self.context.get('request')
        if obj.profile_picture and request:
            return request.build_absolute_uri(obj.profile_picture.url)
        return None

    def resize_image(self, image_field):
        image = Image.open(image_field)
        if image.width > 3000:
            ratio = 3000 / float(image.width)
            height = int((float(image.height) * float(ratio)))
            image = image.resize((3000, height), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            image_format = image_field.name.split('.')[-1].upper()
            if image_format == 'JPG':
                image_format = 'JPEG'
            image.save(buffer, format=image_format)
            return ContentFile(buffer.getvalue(), name=image_field.name)
        return image_field

    def update(self, instance, validated_data):
        profile_picture = validated_data.get('profile_picture', None)
        if profile_picture:
            validated_data['profile_picture'] = self.resize_image(profile_picture)
        return super().update(instance, validated_data)

    def create(self, validated_data):
        profile_picture = validated_data.get('profile_picture', None)
        if profile_picture:
            validated_data['profile_picture'] = self.resize_image(profile_picture)
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
    organization_id = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'organization_id')
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
        organization_id = validated_data.pop("organization_id", None)
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"]
        )

        #added from here to the return value
        if organization_id:
            try:
                org = Organization.objects.get(organizational_id=organization_id)
            except Organization.DoesNotExist:
                raise serializers.ValidationError("Invalid organization ID.")
            profile = user.profile
            profile.organization = org
            profile.role = "unverified"
            profile.subscription_plan = SubscriptionPlan.objects.get(name="multiusers")
            profile.save()

            admin_email = org.admin.user.email
            signer = TimestampSigner()
            token = signer.sign(profile.id)
            #verification_link = f"http://localhost:3000/verify-staff/{token}/"
            verification_link = f"https://naikas.com/verify-staff/{token}/"
            # Send email to admin for verification
            requests.post(
                "https://api.mailgun.net/v3/naikas.com/messages",
                auth=("api", os.environ.get('MAILGUN_API')),
                data={"from": "Naikas <postmaster@naikas.com>",
                    "to": [admin_email],
                    "subject": "Staff Verification Request",
                    "text": f"{user.username} wants to join your organization. Click to verify: {verification_link}"}
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
    

class BulkReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reminder
        fields = [
            "scheduled_date",
            "reminder_methods",
            "recurrence",
            "start_days_before"
        ]


class BulkParticularSerializer(serializers.ModelSerializer):
    reminders = BulkReminderSerializer(many=True)

    class Meta:
        model = Particular
        fields = ["title", "category", "expiry_date", "notes", "reminders"]

    def create(self, validated_data):
        reminders_data = validated_data.pop("reminders", [])
        particular = Particular.objects.create(
            user=self.context["request"].user, **validated_data
        )
        Reminder.objects.bulk_create([
            Reminder(particular=particular, **r) for r in reminders_data
        ])
        return particular


class BulkParticularListSerializer(serializers.Serializer):
    documents = BulkParticularSerializer(many=True)

    def create(self, validated_data):
        user = self.context["request"].user
        created = []
        for doc_data in validated_data["documents"]:
            reminders_data = doc_data.pop("reminders", [])
            particular = Particular.objects.create(user=user, **doc_data)
            Reminder.objects.bulk_create([
                Reminder(particular=particular, **r) for r in reminders_data
            ])
            created.append(particular)
        return created


class OrganizationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['name']
    
    def validate(self, attrs):
        user_profile = self.context['request'].user.profile
        if user_profile.organization:
            raise serializers.ValidationError("You already belong to an organization.")
        return attrs
    
    def create(self, validated_data):
        from django.utils.crypto import get_random_string
        
        user_profile = self.context['request'].user.profile
        
        # Generate unique 6-character organizational ID
        while True:
            org_id = get_random_string(length=6, allowed_chars='0123456789')
            if not Organization.objects.filter(organizational_id=org_id).exists():
                break
        
        organization = Organization.objects.create(
            name=validated_data['name'],
            organizational_id=org_id,
            admin=user_profile
        )
        
        # Assign the user to this organization
        user_profile.organization = organization
        user_profile.role = "admin"
        user_profile.save()
        
        return organization


class StaffSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()
    email = serializers.EmailField(source="user.email", read_only=True)
    joined_at = serializers.DateTimeField(source="user.date_joined", read_only=True)

    class Meta:  
        model = Profile
        fields = ["id", "username", "email", "role", "joined_at"]

    def get_username(self, obj):
        return obj.user.username 


class OrganizationDetailSerializer(serializers.ModelSerializer):
    staff = StaffSerializer(many=True, source="members", read_only=True)  # ✅ use related_name="members"

    class Meta:
        model = Organization
        fields = ["id", "organizational_id", "name", "staff"]
