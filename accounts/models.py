# accounts/models.py

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    email    = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    is_email_verified = models.BooleanField(default=False)

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
    # FIX: default to now so get_or_create never fails with a NOT NULL error
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