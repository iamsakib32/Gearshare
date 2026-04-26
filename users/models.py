from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.files.storage import storages


class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('renter', 'Renter'),
        ('owner', 'Owner'),
        ('admin', 'Admin'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='renter')
    nid_passport_number = models.CharField(max_length=50, blank=True, null=True)
    trust_score = models.FloatField(default=5.0)
    trust_tier = models.CharField(max_length=20, default='Unverified')

    # --- SPRINT 3: LIFECYCLE MANAGEMENT ---
    kyc_attempts = models.IntegerField(default=0)
    suspension_date = models.DateTimeField(null=True, blank=True)

    # --- CLOUD MEDIA FIELDS ---
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)

    kyc_video = models.FileField(
        upload_to='kyc_videos/',
        storage=storages['private_kyc'],  # <--- THE SECURITY LOCK
        blank=True,
        null=True
    )

    def __str__(self):
        return self.username


# ... (keep all your CustomUser code above this) ...

class GearItem(models.Model):
    CONDITION_CHOICES = (
        ('Like New', 'Like New'),
        ('Excellent', 'Excellent'),
        ('Good', 'Good'),
        ('Fair', 'Fair'),
    )

    # Links this item to the specific user who owns it
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='gear_items')

    title = models.CharField(max_length=200)
    description = models.TextField()
    price_per_day = models.DecimalField(max_digits=10, decimal_places=2)
    price_period = models.CharField(max_length=20, default='Day')
    condition = models.CharField(max_length=50, choices=CONDITION_CHOICES, default='Good')

    # Stores the picture of the gear
    image = models.ImageField(upload_to='gear_images/', blank=True, null=True)

    # If the item is currently rented or hidden, the owner can set this to False
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} (Owned by: {self.owner.username})"