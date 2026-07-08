from django.contrib import admin
from django.utils.html import format_html

from import_export.admin import ImportExportMixin

from .models import (
    PaymentTransaction,
    CreditPlan
)


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(ImportExportMixin, admin.ModelAdmin):

    list_display = (
        'id',
        'get_user_display',
        'plan',
        'amount',
        'credits',
        'transaction_type',
        'payment_gateway',
        'status',
        'payment_mode',
        'refund_action',
        'created_at'
    )

    search_fields = (
        'user__email',
        'user__username',
        'razorpay_order_id',
        'razorpay_payment_id'
    )

    list_filter = (
        'status',
        'payment_gateway',
        'transaction_type',
        'created_at'
    )

    ordering = ('-created_at',)

    readonly_fields = (
        'user',
        'plan',
        'transaction_type',
        'payment_gateway',
        'status',
        'amount',
        'credits',
        'razorpay_order_id',
        'razorpay_payment_id',
        'razorpay_signature',
        'payment_mode',
        'card_network',
        'card_number',
        'formatted_gateway_response',
        'failure_reason',
        'paid_at',
        'created_at',
        'updated_at'
    )

    fieldsets = (

        ("User Information", {
            "fields": (
                "user",
                "plan",
            )
        }),

        ("Payment Information", {
            "fields": (
                "transaction_type",
                "payment_gateway",
                "status",
                "amount",
                "credits",
            )
        }),

        ("Razorpay Details", {
            "fields": (
                "razorpay_order_id",
                "razorpay_payment_id",
                "razorpay_signature",
            )
        }),

        ("Card / Payment Mode", {
            "fields": (
                "payment_mode",
                "card_network",
                "card_number",
            )
        }),

        ("Gateway Response", {
            "fields": (
                "formatted_gateway_response",
                "failure_reason",
            )
        }),

        ("Timestamps", {
            "fields": (
                "paid_at",
                "created_at",
                "updated_at",
            )
        }),
    )

    def get_user_display(self, obj):

        if obj.user and obj.user.email:
            return obj.user.email

        if obj.user and obj.user.username:
            return obj.user.username

        return "-"

    get_user_display.short_description = "User"

    def refund_action(self, obj):

        if (
            obj.status == "SUCCESS"
            and obj.razorpay_payment_id
        ):

            return format_html(
                '''
                <a class="button"
                   href="/payments/admin/refund/?payment_id={}">
                   Refund
                </a>
                ''',
                obj.razorpay_payment_id
            )

        elif obj.status == "REFUNDED":

            return format_html(
                '<span style="color:red;">Refunded</span>'
            )

        return "-"

    refund_action.short_description = "Refund"

    def formatted_gateway_response(self, obj):

        import json

        if not obj.gateway_response:
            return "-"

        formatted_json = json.dumps(
            obj.gateway_response,
            indent=4
        )

        return format_html(
            "<pre>{}</pre>",
            formatted_json
        )

    formatted_gateway_response.short_description = (
        "Gateway Response"
    )


@admin.register(CreditPlan)
class CreditPlanAdmin(
    ImportExportMixin,
    admin.ModelAdmin
):

    list_display = (
        'id',
        'name',
        'price',
        'credits',
        'validity_days',
        'offer_percent',
        'is_active',
        'display_order',
    )

    list_filter = (
        'is_active',
    )

    search_fields = (
        'name',
    )

    ordering = (
        'display_order',
    )