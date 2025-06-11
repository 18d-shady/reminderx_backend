from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import *

urlpatterns = [
    path('api/register/', RegisterView.as_view(), name='register'),
    # Auth
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Core APIs
    path('api/me/', current_user_view, name='current-user'),
    path('api/particulars/', ParticularListCreateView.as_view(), name='particulars'),
    path('api/particulars/<int:pk>/', ParticularDetailUpdateView.as_view(), name='particular-detail'),
    path('api/particulars/search/', ParticularSearchView.as_view(), name='particular-search'),
    path('api/reminders/', ReminderListCreateView.as_view(), name='reminders'),
    path('api/reminders/<int:pk>/', ReminderUpdateView.as_view(), name='update-reminder'),
    path('api/notifications/', NotificationListView.as_view(), name='notification-list'),
]
