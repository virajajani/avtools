from rest_framework import serializers
from .models import CreditPlan, PaymentTransaction


class CreditPlanSerializer(serializers.ModelSerializer):

    final_price = serializers.SerializerMethodField()

    class Meta:
        model = CreditPlan
        fields = [
            "id",
            "name",
            "price",
            "credits",
            "validity_days",
            "offer_percent",
            "final_price",
            "description",
            "is_active",
        ]

    def get_final_price(self, obj):

        if obj.offer_percent > 0:
            discount = (obj.price * obj.offer_percent) / 100
            return obj.price - discount

        return obj.price


class PaymentTransactionSerializer(serializers.ModelSerializer):

    username = serializers.CharField(
        source="user.username",
        read_only=True
    )

    email = serializers.EmailField(
        source="user.email",
        read_only=True
    )

    transaction_type_display = serializers.CharField(
        source="get_transaction_type_display",
        read_only=True
    )

    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True
    )

    payment_gateway_display = serializers.CharField(
        source="get_payment_gateway_display",
        read_only=True
    )

    plan_name = serializers.CharField(
        source="plan.name",
        read_only=True
    )

    class Meta:
        model = PaymentTransaction
        fields = [
            "id",
            "username",
            "email",
            "plan_name",
            "amount",
            "credits",
            "transaction_type",
            "transaction_type_display",
            "payment_gateway",
            "payment_gateway_display",
            "status",
            "status_display",
            "razorpay_order_id",
            "razorpay_payment_id",
            "payment_mode",
            "card_network",
            "paid_at",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "paid_at",
        ]