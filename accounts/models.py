# accounts/models.py

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):

    AUTH_PROVIDER_CHOICES = (
        ("EMAIL",  "Email / Password"),
        ("GOOGLE", "Google"),
    )

    email             = models.EmailField(unique=True)
    username          = models.CharField(max_length=150, unique=True)
    is_email_verified = models.BooleanField(default=False)

    # ── Google / Firebase auth fields ──────────────────────────────
    auth_provider = models.CharField(
        max_length=10,
        choices=AUTH_PROVIDER_CHOICES,
        default="EMAIL",
    )
    google_uid = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        unique=True,
        help_text="Firebase UID for users who signed up/logged in via Google.",
    )
    profile_picture_url = models.URLField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Google profile photo URL, if available.",
    )

    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.email


class UserDevice(models.Model):
    user         = models.ForeignKey(User, on_delete=models.CASCADE)
    device_id    = models.CharField(max_length=255)
    last_login   = models.DateTimeField(auto_now=True)
    token_expiry = models.DateTimeField()

    def is_expired(self):
        return timezone.now() > self.token_expiry

    def __str__(self):
        return f"{self.user.email} — {self.device_id}"


class UserCredit(models.Model):
    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name="credit")
    balance    = models.IntegerField(default=0)
    expires_at = models.DateTimeField(default=timezone.now)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"{self.user.email} — {self.balance} credits"


class EmailOTP(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE)
    otp        = models.CharField(max_length=6)
    expires_at = models.DateTimeField()

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"{self.user.email} — OTP"


class ContactSupport(models.Model):
    first_name    = models.CharField(max_length=100)
    last_name     = models.CharField(max_length=100, null=True, blank=True)
    mobile_number = models.CharField(max_length=15, null=True, blank=True)
    email         = models.EmailField()
    message       = models.TextField()
    created_at    = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name or ''} — {self.email}"


class CreditHistory(models.Model):

    TRANSACTION_TYPES = (
        ("ADD",    "Add Credit"),
        ("DEDUCT", "Deduct Credit"),
        ("REFUND", "Refund Credit"),
        ("EXPIRE", "Expire Credit"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="credit_history"
    )

    credits = models.IntegerField()

    transaction_type = models.CharField(
        max_length=10,
        choices=TRANSACTION_TYPES
    )

    previous_balance = models.IntegerField(default=0)
    current_balance  = models.IntegerField(default=0)

    description = models.TextField(null=True, blank=True)

    payment_id = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} - {self.transaction_type} - {self.credits}"


class DeviceRegistration(models.Model):
    device_fingerprint = models.CharField(max_length=255, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')
    registered_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        verbose_name = "Device Registration"

    def __str__(self):
        return f"{self.user.email} — {self.device_fingerprint[:20]}"


class ProductReview(models.Model):
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]

    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    rating     = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    comment    = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_visible = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Product Review"

    def __str__(self):
        return f"{self.user.email} — {self.rating}★"