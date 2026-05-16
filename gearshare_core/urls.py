from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from users import views
from users.views import rental_contract_page

urlpatterns = [
    path('admin/', admin.site.urls),

    # Prefix for all internal API logic
    path('api/users/', include('users.urls')),

    path('rental-contract/<int:request_id>/', rental_contract_page, name='rental_contract_page'),

    # THE FIX: Moved chat here to make it a top-level visual page
    path('rentals/<int:request_id>/chat/', views.rental_chat_page, name='rental_chat_page'),

    # Visual Pages
    path('', TemplateView.as_view(template_name='index.html'), name='home'),
    path('login/', TemplateView.as_view(template_name='login.html'), name='visual_login'),
    path('register/', TemplateView.as_view(template_name='register.html'), name='visual_register'),
    path('dashboard/', TemplateView.as_view(template_name='dashboard.html'), name='dashboard'),

    # Equipment Pages
    path('gear/<int:item_id>/', views.gear_detail_page, name='gear_detail_page'),
    path('edit-gear/<int:item_id>/', views.edit_gear_page, name='edit_gear_page'),
    path('add-gear/', views.add_gear_page, name='add_gear_page'),
]