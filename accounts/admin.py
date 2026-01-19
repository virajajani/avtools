from django.contrib import admin
from .models import User, UserDevice, UserCredit, EmailOTP

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "is_email_verified", "is_staff", "is_active")
    search_fields = ("email",)
    ordering = ("email",)

@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "device_id", "last_login", "token_expiry")
    search_fields = ("device_id",)

@admin.register(UserCredit)
class UserCreditAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "expires_at")

@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ("user", "otp", "expires_at")
