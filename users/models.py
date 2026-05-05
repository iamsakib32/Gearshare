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

    kyc_attempts = models.IntegerField(default=0)
    suspension_date = models.DateTimeField(null=True, blank=True)

    transaction_count = models.IntegerField(default=0)

    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)

    kyc_video = models.FileField(
        upload_to='kyc_videos/',
        storage=storages['private_kyc'],
        blank=True,
        null=True
    )

    can_switch_role = models.BooleanField(default=False)
    role_status_msg = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.username


class GearItem(models.Model):
    CONDITION_CHOICES = (
        ('Like New', 'Like New'), ('Excellent', 'Excellent'),
        ('Good', 'Good'), ('Fair', 'Fair'),
    )

    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='gear_items')
    title = models.CharField(max_length=200)
    description = models.TextField()
    price_per_day = models.DecimalField(max_digits=10, decimal_places=2)
    price_period = models.CharField(max_length=20, default='Day')
    condition = models.CharField(max_length=50, choices=CONDITION_CHOICES, default='Good')

    # This acts as the mandatory cover photo
    image = models.ImageField(upload_to='gear_images/', blank=True, null=True)
    is_active = models.BooleanField(default=True)

    category = models.CharField(max_length=50, default='Other')
    replacement_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    min_rental_duration = models.CharField(max_length=50, default='1 day')
    available_days = models.CharField(max_length=100, default='S,M,T,W,Th,F,Sa')
    delivery_option = models.CharField(max_length=50, default='Pickup only')
    pickup_location = models.CharField(max_length=255, blank=True, null=True)
    cancellation_policy = models.CharField(max_length=50, default='flexible')

    min_trust_tier = models.IntegerField(default=7)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} (Owned by: {self.owner.username})"


# --- CLOUD GALLERY MODEL ---
class GearGallery(models.Model):
    # This links the extra 2 to 4 photos directly back to the specific GearItem
    gear = models.ForeignKey(GearItem, on_delete=models.CASCADE, related_name='gallery_images')
    image = models.ImageField(upload_to='gear_gallery/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Gallery Photo for {self.gear.title}"


class RoleSwitchRequest(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='role_switch_requests')
    current_role = models.CharField(max_length=10)
    requested_role = models.CharField(max_length=10)
    status = models.CharField(max_length=20, default='Pending')

    product_name = models.CharField(max_length=200, blank=True, null=True)
    product_image = models.ImageField(upload_to='role_request_products/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} wants to be {self.requested_role}"


# --- NEW: RENTAL REQUEST & CHAT BASELINE ---
class RentalRequest(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Declined', 'Declined'),
        ('Completed', 'Completed'),
    )

    gear = models.ForeignKey(GearItem, on_delete=models.CASCADE, related_name='rental_requests')
    renter = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='rentals_made')
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='rentals_received')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Request: {self.renter.username} -> {self.gear.title}"