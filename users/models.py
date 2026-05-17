from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.files.storage import storages
from django.utils import timezone


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

    # Google Auth and OTP Security
    google_id = models.CharField(max_length=200, blank=True, null=True, unique=True)
    auth_provider = models.CharField(max_length=50, default='email', null=True, blank=True)
    otp_code = models.CharField(max_length=6, blank=True, null=True)
    otp_expiration = models.DateTimeField(blank=True, null=True)
    otp_failed_attempts = models.IntegerField(default=0)

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

    image = models.ImageField(upload_to='gear_images/', blank=True, null=True)
    is_active = models.BooleanField(default=True)

    category = models.CharField(max_length=50, default='Other')
    replacement_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    min_rental_duration = models.CharField(max_length=50, default='1 day')
    available_days = models.CharField(max_length=100, default='S,M,T,W,Th,F,Sa')
    delivery_option = models.CharField(max_length=50, default='Pickup only')
    pickup_location = models.CharField(max_length=255, blank=True, null=True)
    cancellation_policy = models.CharField(max_length=50, default='flexible')

    is_negotiable = models.BooleanField(default=True)
    min_trust_tier = models.IntegerField(default=1)

    location = models.CharField(max_length=100, blank=True, null=True)
    area = models.CharField(max_length=100, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} (Owned by: {self.owner.username})"


class GearGallery(models.Model):
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
    negotiated_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    # Evidence Vault integration
    renter_agreed_price = models.BooleanField(default=False)
    evidence_uploaded = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Request: {self.renter.username} -> {self.gear.title}"


class RentalEvidence(models.Model):
    rental_request = models.ForeignKey(RentalRequest, on_delete=models.CASCADE, related_name='evidence_photos')
    image = models.ImageField(upload_to='evidence_vault/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Evidence for Req #{self.rental_request.id}"


class ChatMessage(models.Model):
    rental_request = models.ForeignKey(RentalRequest, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    text = models.TextField()

    is_system_update = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Msg from {self.sender.username} on Req #{self.rental_request.id}"


#  TRUST SCORE ENGINE CONSTANTS & LEDGER


class EventType(models.TextChoices):
    RENTAL_COMPLETED   = 'rental_completed',   'Rental Completed'
    POSITIVE_REVIEW    = 'positive_review',    'Positive Review (4–5★)'
    ON_TIME_RETURN     = 'on_time_return',     'On-Time Return'
    KYC_VERIFIED       = 'kyc_verified',       'KYC Verified'
    LATE_RETURN        = 'late_return',        'Late Return (per day)'
    LAST_MIN_CANCEL    = 'last_min_cancel',    'Last-Minute Cancellation'
    POOR_REVIEW        = 'poor_review',        'Poor Review (1–2★)'
    DISPUTE_LOST_MINOR = 'dispute_lost_minor', 'Dispute Lost (minor)'
    DISPUTE_LOST_MAJOR = 'dispute_lost_major', 'Dispute Lost (major)'
    INACTIVITY_DECAY   = 'inactivity_decay',   'Inactivity Decay'
    ADMIN_ADJUSTMENT   = 'admin_adjustment',   'Admin Manual Adjustment'

SCORE_DELTAS = {
    EventType.RENTAL_COMPLETED:   +0.10,
    EventType.POSITIVE_REVIEW:    +0.20,
    EventType.ON_TIME_RETURN:     +0.05,
    EventType.KYC_VERIFIED:       None,
    EventType.LATE_RETURN:        -0.50,
    EventType.LAST_MIN_CANCEL:    -1.00,
    EventType.POOR_REVIEW:        -0.80,
    EventType.DISPUTE_LOST_MINOR: -3.00,
    EventType.DISPUTE_LOST_MAJOR: -5.00,
    EventType.INACTIVITY_DECAY:   -0.10,
    EventType.ADMIN_ADJUSTMENT:   None,
}

TIER_THRESHOLDS = [
    (8.0,  'Elite'),
    (6.0,  'Verified'),
    (4.0,  'Restricted'),
    (0.0,  'Suspended'),
]

TIER_LEVELS = {
    'Suspended':  0,
    'Restricted': 1,
    'Verified':   2,
    'Elite':      3,
}

# Max score logic
SCORE_MIN = 0.0
SCORE_MAX = 10.0

class ScoreEvent(models.Model):
    # Immutable log. Every score change gets recorded here for security.
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='score_events')
    event_type  = models.CharField(max_length=40, choices=EventType.choices)
    delta       = models.FloatField()
    score_before = models.FloatField()
    score_after  = models.FloatField()
    tier_before  = models.CharField(max_length=20)
    tier_after   = models.CharField(max_length=20)
    rental_request_id = models.IntegerField(null=True, blank=True)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        indexes  = [models.Index(fields=['user', '-created_at'])]