from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.files.storage import storages  # <--- NEW IMPORT


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

    # --- CLOUD MEDIA FIELDS ---

    # Uses the "default" public storage bucket automatically
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)

    # FORCE Django to use the Private Vault storage for this specific field
    kyc_video = models.FileField(
        upload_to='kyc_videos/',
        storage=storages['private_kyc'],  # <--- THE SECURITY LOCK
        blank=True,
        null=True
    )

    def __str__(self):
        return self.username