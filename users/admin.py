from django.contrib import admin
from .models import CustomUser, GearItem

# Register your models here.
admin.site.register(CustomUser)
admin.site.register(GearItem)