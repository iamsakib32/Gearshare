from django.urls import path
from .views import (RegisterView, LoginView, PendingKYCView, ApproveKYCView, DeclineKYCView, ResubmitKYCView,
                    GearListView, add_gear_page,
                    AddGearAPIView, edit_gear_page, GearDetailAPIView, gear_detail_page, get_single_gear_api)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),

    # --- ADMIN & LIFECYCLE ENDPOINTS ---
    path('kyc-pending/', PendingKYCView.as_view(), name='kyc_pending'),
    path('kyc-approve/<int:user_id>/', ApproveKYCView.as_view(), name='kyc_approve'),
    path('kyc-decline/<int:user_id>/', DeclineKYCView.as_view(), name='kyc_decline'),
    path('kyc-resubmit/<int:user_id>/', ResubmitKYCView.as_view(), name='kyc_resubmit'),
    path('gear/', GearListView.as_view(), name='gear_list'),
    path('add-gear/', add_gear_page, name='add_gear_page'),
    path('api/users/gear/add/', AddGearAPIView.as_view(), name='api_add_gear'),

    # Kept for Edit and Delete features
    path('edit-gear/<int:item_id>/', edit_gear_page, name='edit_gear_page'),
    path('api/users/gear/<int:item_id>/', GearDetailAPIView.as_view(), name='api_gear_detail'),

    # NEW: Safely get gear info for the public detail page!
    path('api/users/gear/info/<int:item_id>/', get_single_gear_api, name='api_single_gear_info'),

    # The actual visual page
    path('gear/<int:item_id>/', gear_detail_page, name='gear_detail_page'),
]