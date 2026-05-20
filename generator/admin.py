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

@admin.register(GenerationHistory)
class GenerationHistoryAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "user",
        "get_categories",
        "meesho_price",
        "image_preview",
        "created_at",
    )

    readonly_fields = (
        "image_preview",
        "uploaded_image",
        "created_at",
    )

    search_fields = (
        "user__email",
        "categories__name",
    )

    list_filter = (
        "created_at",
        "categories",
    )

    ordering = (
        "-created_at",
    )

    filter_horizontal = (
        "categories",
    )

    # ===============================
    # CATEGORY LIST
    # ===============================

    def get_categories(self, obj):

        return ", ".join([
            category.name
            for category in obj.categories.all()
        ])

    get_categories.short_description = "Categories"

    # ===============================
    # IMAGE PREVIEW
    # ===============================

    def image_preview(self, obj):

        if obj.uploaded_image:

            return format_html(
                '''
                <img
                    src="{}"
                    style="
                        width:100px;
                        height:100px;
                        object-fit:cover;
                        border-radius:10px;
                        border:1px solid #ddd;
                    "
                />
                ''',
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