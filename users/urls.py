from django.urls import path
from .views import (RegisterView, PendingKYCView, ApproveKYCView,
                    DeclineKYCView, ResubmitKYCView, GearListView, AddGearAPIView,
                    GearDetailAPIView, get_single_gear_api, SubmitRoleSwitchAPIView,
                    PendingRoleSwitchAPIView, ApproveRoleSwitchAPIView,
                    DeclineRoleSwitchAPIView, ToggleRoleAPIView, CheckRoleStatusAPIView,
                    SubmitRentalRequestAPIView, ChatHistoryAPIView,
                    UpdateChatPriceAPIView, UserChatListAPIView,
                    SendLoginOTPView, VerifyLoginOTPView, SendResetOTPView, ResetPasswordWithOTPView,
                    GoogleLoginRedirectView, GoogleAuthCallbackView, AgreeToPriceAPIView,
                    UploadEvidenceAPIView, GetEvidenceAPIView,
                    ApproveRentalView, CompleteRentalView, CancelRentalView,
                    ApplyTrustEventView, AdminAdjustTrustView, TrustHistoryView, TrustProfileView)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),

    path('otp/send-login/', SendLoginOTPView.as_view(), name='otp_send_login'),
    path('otp/verify-login/', VerifyLoginOTPView.as_view(), name='otp_verify_login'),
    path('otp/send-reset/', SendResetOTPView.as_view(), name='otp_send_reset'),
    path('otp/reset-password/', ResetPasswordWithOTPView.as_view(), name='otp_reset_password'),

    path('auth/google/', GoogleLoginRedirectView.as_view(), name='google_login'),
    path('auth/google/callback/', GoogleAuthCallbackView.as_view(), name='google_callback'),

    path('kyc-pending/', PendingKYCView.as_view(), name='kyc_pending'),
    path('kyc-approve/<int:user_id>/', ApproveKYCView.as_view(), name='kyc_approve'),
    path('kyc-decline/<int:user_id>/', DeclineKYCView.as_view(), name='kyc_decline'),
    path('kyc-resubmit/<int:user_id>/', ResubmitKYCView.as_view(), name='kyc_resubmit'),

    path('gear/', GearListView.as_view(), name='gear_list'),
    path('gear/add/', AddGearAPIView.as_view(), name='api_add_gear'),
    path('gear/update/<int:item_id>/', GearDetailAPIView.as_view(), name='api_gear_detail'),
    path('gear/info/<int:item_id>/', get_single_gear_api, name='api_single_gear_info'),

    path('role-switch/submit/<int:user_id>/', SubmitRoleSwitchAPIView.as_view(), name='role_switch_submit'),
    path('role-switch/pending/', PendingRoleSwitchAPIView.as_view(), name='role_switch_pending'),
    path('role-switch/approve/<int:request_id>/', ApproveRoleSwitchAPIView.as_view(), name='role_switch_approve'),
    path('role-switch/decline/<int:request_id>/', DeclineRoleSwitchAPIView.as_view(), name='role_switch_decline'),
    path('role-switch/toggle/<int:user_id>/', ToggleRoleAPIView.as_view(), name='role_switch_toggle'),
    path('role-switch/check/<int:user_id>/', CheckRoleStatusAPIView.as_view(), name='role_switch_check'),

    path('rental/request/', SubmitRentalRequestAPIView.as_view(), name='api_submit_rental_request'),
    path('rental/<int:request_id>/messages/', ChatHistoryAPIView.as_view(), name='api_chat_history'),
    path('rental/<int:request_id>/update-price/', UpdateChatPriceAPIView.as_view(), name='api_update_chat_price'),
    path('rental/<int:request_id>/agree-price/', AgreeToPriceAPIView.as_view(), name='api_agree_price'),
    path('rental/<int:request_id>/upload-evidence/', UploadEvidenceAPIView.as_view(), name='api_upload_evidence'),
    path('rental/<int:request_id>/evidence/', GetEvidenceAPIView.as_view(), name='api_get_evidence'),
    path('chats/<int:user_id>/', UserChatListAPIView.as_view(), name='api_user_chat_list'),

    # Trust Engine / Rental Flow API hooks
    path('rental/<int:request_id>/approve/', ApproveRentalView.as_view(), name='api_approve_rental'),
    path('rental/<int:request_id>/complete/', CompleteRentalView.as_view(), name='api_complete_rental'),
    path('rental/<int:request_id>/cancel/', CancelRentalView.as_view(), name='api_cancel_rental'),

    path('trust/event/', ApplyTrustEventView.as_view(), name='trust_event'),
    path('trust/admin-adjust/', AdminAdjustTrustView.as_view(), name='trust_admin_adjust'),
    path('trust/history/<int:user_id>/', TrustHistoryView.as_view(), name='trust_history'),
    path('trust/profile/<int:user_id>/', TrustProfileView.as_view(), name='trust_profile'),
]