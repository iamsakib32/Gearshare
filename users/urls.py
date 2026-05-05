from django.urls import path
from .views import (RegisterView, LoginView, PendingKYCView, ApproveKYCView,
                    DeclineKYCView, ResubmitKYCView, GearListView, AddGearAPIView,
                    GearDetailAPIView, get_single_gear_api, SubmitRoleSwitchAPIView,
                    PendingRoleSwitchAPIView, ApproveRoleSwitchAPIView,
                    DeclineRoleSwitchAPIView, ToggleRoleAPIView,
                    SubmitRentalRequestAPIView, GenerateContractPDFView, ContractPageView)  # Removed rental_chat_page import from here

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),

    # Admin & Lifecycle
    path('kyc-pending/', PendingKYCView.as_view(), name='kyc_pending'),
    path('kyc-approve/<int:user_id>/', ApproveKYCView.as_view(), name='kyc_approve'),
    path('kyc-decline/<int:user_id>/', DeclineKYCView.as_view(), name='kyc_decline'),
    path('kyc-resubmit/<int:user_id>/', ResubmitKYCView.as_view(), name='kyc_resubmit'),

    # Gear API (Prefix 'api/users/' added by gearshare_core/urls.py)
    path('gear/', GearListView.as_view(), name='gear_list'),
    path('gear/add/', AddGearAPIView.as_view(), name='api_add_gear'),
    path('gear/update/<int:item_id>/', GearDetailAPIView.as_view(), name='api_gear_detail'),
    path('gear/info/<int:item_id>/', get_single_gear_api, name='api_single_gear_info'),

    # Role Switching
    path('role-switch/submit/<int:user_id>/', SubmitRoleSwitchAPIView.as_view(), name='role_switch_submit'),
    path('role-switch/pending/', PendingRoleSwitchAPIView.as_view(), name='role_switch_pending'),
    path('role-switch/approve/<int:request_id>/', ApproveRoleSwitchAPIView.as_view(), name='role_switch_approve'),
    path('role-switch/decline/<int:request_id>/', DeclineRoleSwitchAPIView.as_view(), name='role_switch_decline'),
    path('role-switch/toggle/<int:user_id>/', ToggleRoleAPIView.as_view(), name='role_switch_toggle'),

    # Submit Request API
    path('rental/request/', SubmitRentalRequestAPIView.as_view(), name='api_submit_rental_request'),
    path('generate-contract/', GenerateContractPDFView.as_view(), name='generate_contract'),
    path('view-contract/', ContractPageView.as_view(), name='view_contract'),
]