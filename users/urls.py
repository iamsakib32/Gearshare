from django.urls import path
from .views import RegisterView, LoginView, PendingKYCView, ApproveKYCView, DeclineKYCView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),

    # --- ADMIN ENDPOINTS ---
    path('kyc-pending/', PendingKYCView.as_view(), name='kyc_pending'),
    path('kyc-approve/<int:user_id>/', ApproveKYCView.as_view(), name='kyc_approve'),
    path('kyc-decline/<int:user_id>/', DeclineKYCView.as_view(), name='kyc_decline'),
]