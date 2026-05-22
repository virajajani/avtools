# payments/models.py

from django.db import models
from accounts.models import User


class CreditPlan(models.Model):

    PLAN_TYPES = (
        ("STARTER", "Starter"),
        ("GROWTH", "Growth"),
        ("PRO", "Pro"),
    )

    name = models.CharField(
        max_length=50,
        choices=PLAN_TYPES,
        unique=True
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    credits = models.PositiveIntegerField()

    validity_days = models.PositiveIntegerField(
        default=30
    )

    offer_percent = models.PositiveIntegerField(
        default=0
    )

    is_active = models.BooleanField(
        default=True
    )

    display_order = models.PositiveIntegerField(
        default=1
    )

    description = models.TextField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["display_order"]

    def __str__(self):
        return f"{self.name} - ₹{self.price}"


class PaymentTransaction(models.Model):

    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
        ("REFUNDED", "Refunded"),
    )

    PAYMENT_GATEWAYS = (
        ("RAZORPAY", "Razorpay"),
        ("PAYU", "PayU"),
    )

    TRANSACTION_TYPES = (
        ("CREDIT_PURCHASE", "Credit Purchase"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="payments"
    )

    plan = models.ForeignKey(
        CreditPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    transaction_type = models.CharField(
        max_length=30,
        choices=TRANSACTION_TYPES,
        default="CREDIT_PURCHASE"
    )

    payment_gateway = models.CharField(
        max_length=20,
        choices=PAYMENT_GATEWAYS,
        default="RAZORPAY"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    credits = models.PositiveIntegerField(
        default=0
    )

    razorpay_order_id = models.CharField(
        max_length=255,
        unique=True
    )

    razorpay_payment_id = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    razorpay_signature = models.TextField(
        blank=True,
        null=True
    )

    payment_mode = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    card_network = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    card_number = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    gateway_response = models.JSONField(
        default=dict,
        blank=True,
        null=True
    )

    failure_reason = models.TextField(
        blank=True,
        null=True
    )

    paid_at = models.DateTimeField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["user"]),
            models.Index(fields=["razorpay_order_id"]),
        ]

    def __str__(self):
        return f"{self.user.username} - ₹{self.amount} - {self.status}"