from django.contrib import admin
from .models import UserProfile, GenerationHistory, ActiveSession
from django.utils.html import format_html

# ===============================
# User Profile Admin
# ===============================
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "credits")
    search_fields = ("user__username", "user__email", "display_name")
    list_editable = ("credits",)
    list_filter = ("credits",)


# ===============================
# Generation History Admin
# ===============================
@admin.register(GenerationHistory)
class GenerationHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "category",
        "image_preview",   # ✅ ADD THIS
        "created_at",
    )

    readonly_fields = ("image_preview", "uploaded_image", "created_at")

    # ✅ IMAGE PREVIEW FUNCTION
    def image_preview(self, obj):
        if obj.uploaded_image:
            return format_html(
                '<img src="{}" style="width: 100px; height: auto;" />',
                obj.uploaded_image.url
            )
        return "No Image"

    image_preview.short_description = "Preview"



# ===============================
# Active Sessions Admin
# ===============================
@admin.register(ActiveSession)
class ActiveSessionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "ip_address",
        "session_key",
        "last_activity",
    )
    search_fields = ("user__username", "ip_address")
    readonly_fields = ("session_key", "last_activity")
    ordering = ("-last_activity",)