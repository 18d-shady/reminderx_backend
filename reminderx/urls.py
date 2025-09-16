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
    path("api/create-organization/", CreateOrganizationView.as_view(), name="create-organization"),
    path("api/verify-organization/", VerifyOrganizationView.as_view(), name="verify-organization"),
    path("api/verify-staff/", VerifyStaffView.as_view(), name="verify-staff"),
    path("api/organizations/<str:organizational_id>/", OrganizationDetailView.as_view(), name="organization-detail"),

]
