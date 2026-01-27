from django.contrib import admin
from .models import (
    User,
    UserDevice,
    UserCredit,
    EmailOTP,
    ContactSupport
)

# =========================
# USER ADMIN
# =========================
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "username",
        "is_email_verified",
        "is_staff",
        "is_active",
        "date_joined",
    )
    search_fields = ("email", "username")
    ordering = ("-date_joined",)
    list_filter = ("is_email_verified", "is_staff", "is_active")
    readonly_fields = ("last_login", "date_joined")


# =========================
# USER DEVICE ADMIN
# =========================
@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "device_id",
        "last_login",
        "token_expiry",
        "is_token_expired",
    )
    search_fields = ("device_id", "user__email")
    list_filter = ("token_expiry",)
    readonly_fields = ("last_login",)

    def is_token_expired(self, obj):
        return obj.is_expired()
    is_token_expired.boolean = True
    is_token_expired.short_description = "Token Expired"


# =========================
# USER CREDIT ADMIN
# =========================
@admin.register(UserCredit)
class UserCreditAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "balance",
        "expires_at",
        "is_credit_expired",
    )
    search_fields = ("user__email",)
    list_filter = ("expires_at",)

    def is_credit_expired(self, obj):
        return obj.is_expired()
    is_credit_expired.boolean = True
    is_credit_expired.short_description = "Expired"


# =========================
# EMAIL OTP ADMIN
# =========================
@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "otp",
        "expires_at",
        "is_otp_expired",
    )
    search_fields = ("user__email", "otp")
    list_filter = ("expires_at",)

    def is_otp_expired(self, obj):
        return obj.is_expired()
    is_otp_expired.boolean = True
    is_otp_expired.short_description = "Expired"


# =========================
# CONTACT SUPPORT ADMIN
# =========================
@admin.register(ContactSupport)
class ContactSupportAdmin(admin.ModelAdmin):
    list_display = (
        "first_name",
        "last_name",
        "email",
        "mobile_number",
        "created_at",
    )
    search_fields = (
        "first_name",
        "last_name",
        "email",
        "mobile_number",
        "message",
    )
    list_filter = ("created_at",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
