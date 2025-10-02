from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import *

urlpatterns = [
    #firebase
    path('api/fcm-token/', RegisterFCMTokenView.as_view(), name='register-fcm-token'),

    #register
    path('api/register/', RegisterView.as_view(), name='register'),
    path('api/verify-email/', SendVerificationEmail.as_view(), name='verify_email'),

    # Auth
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Core APIs
    path('api/me/', current_user_view, name='current-user'),
    path('api/particulars/', ParticularListCreateView.as_view(), name='particulars'),
    path('api/particulars/<int:pk>/', ParticularDetailUpdateView.as_view(), name='particular-detail'),
    path('api/particulars/search/', ParticularSearchView.as_view(), name='particular-search'),
    path('api/reminders/', ReminderListCreateView.as_view(), name='reminders'),
    path('api/reminders/<int:pk>/', ReminderUpdateView.as_view(), name='update-reminder'),
    path('api/notifications/', NotificationListView.as_view(), name='notification-list'),
    path('api/bulk-create/', BulkParticularCreateView.as_view(), name='bulk-create'),
    path("api/manual-upgrade/", manual_upgrade, name="manual-upgrade"),

     # Organization & Staff Management
    path("api/create-organization/", CreateOrganizationView.as_view(), name="create-organization"),
    path("api/verify-organization/", VerifyOrganizationView.as_view(), name="verify-organization"),
    path("api/verify-staff/", VerifyStaffView.as_view(), name="verify-staff"),
    path("api/organizations/<str:organizational_id>/", OrganizationDetailView.as_view(), name="organization-detail"),
    path("api/particulars/<int:particular_id>/owners/", manage_particular_owner, name="manage_particular_owner"),
    path("api/staff/<int:profile_id>/particulars/", staff_particulars_view, name="staff_particulars"),
    path("api/staff/<int:profile_id>/send-message/", send_message_view, name="send_message"),
    path("api/staff/<int:profile_id>/delete/", delete_staff_view, name="delete-staff"),
    path("api/organizations/<str:org_id>/set-icon/", set_organization_icon, name="set-organization-icon"),

    #payment
    path("api/paystack/init/", PaystackInitView.as_view()),
    path("api/paystack/verify/<str:reference>/", PaystackVerifyView.as_view()),

]
