from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import ParticularListCreateView, ReminderListCreateView, RegisterView

urlpatterns = [
    path('api/register/', RegisterView.as_view(), name='register'),
    # Auth
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Core APIs
    path('api/particulars/', ParticularListCreateView.as_view(), name='particulars'),
    path('api/reminders/', ReminderListCreateView.as_view(), name='reminders'),
]
