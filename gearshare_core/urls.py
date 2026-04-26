"""
URL configuration for gearshare_core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from users.views import add_gear_page, AddGearAPIView, GearDetailAPIView
from users import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')),
    path('', TemplateView.as_view(template_name='index.html'), name='home'),
    path('login/', TemplateView.as_view(template_name='login.html'), name='visual_login'),
    path('register/', TemplateView.as_view(template_name='register.html'), name='visual_register'),
    path('dashboard/', TemplateView.as_view(template_name='dashboard.html'), name='dashboard'),
    path('add-gear/', add_gear_page, name='add_gear_page'),
    path('edit-gear/<int:item_id>/', views.edit_gear_page, name='edit_gear_page'),
    path('api/users/gear/add/', AddGearAPIView.as_view(), name='api_add_gear'),
    path('api/users/gear/update/<int:item_id>/', GearDetailAPIView.as_view(), name='api_gear_detail'),
    path('gear/<int:item_id>/', views.gear_detail_page, name='gear_detail_page'),
    path('api/users/gear/info/<int:item_id>/', views.get_single_gear_api, name='api_single_gear_info'),
]
