import razorpay
from datetime import timedelta

from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import generics, filters

from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as django_filters

from .models import CreditPlan, PaymentTransaction
from .serializers import (
    CreditPlanSerializer,
    PaymentTransactionSerializer,
)

from accounts.models import UserCredit
from rest_framework.permissions import AllowAny

# ---------------------------------------------------------------------------
# Razorpay Client
# ---------------------------------------------------------------------------
razorpay_client = razorpay.Client(
    auth=(
        settings.RAZORPAY_API_KEY,
        settings.RAZORPAY_API_SECRET_KEY,
    )
)


# ===========================================================================
# CREDIT PLANS  —  GET /api/payments/credit-plans/
# ===========================================================================

@api_view(["GET"])
@permission_classes([AllowAny])
def get_credit_plans(request):
    plans = CreditPlan.objects.filter(
        is_active=True
    ).order_by("display_order")

    serializer = CreditPlanSerializer(plans, many=True)
    return Response(serializer.data)


# ===========================================================================
# CREATE ORDER  —  POST /api/payments/create-order/
# ===========================================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_order(request):
    try:
        plan_name = request.data.get("plan")

        if not plan_name:
            return JsonResponse({"error": "plan is required"}, status=400)

        plan = CreditPlan.objects.filter(name=plan_name, is_active=True).first()

        if not plan:
            return JsonResponse({"error": "Invalid or inactive plan"}, status=400)

        # Apply discount if any
        if plan.offer_percent > 0:
            discount = (plan.price * plan.offer_percent) / 100
            final_price = plan.price - discount
        else:
            final_price = plan.price

        # Razorpay expects paisa (integer)
        amount_in_paisa = int(final_price * 100)

        razorpay_order = razorpay_client.order.create(
            {
                "amount": amount_in_paisa,
                "currency": "INR",
                "payment_capture": 1,   # auto-capture
            }
        )

        PaymentTransaction.objects.create(
            user=request.user,
            plan=plan,
            amount=final_price,
            credits=plan.credits,
            razorpay_order_id=razorpay_order["id"],
            transaction_type="CREDIT_PURCHASE",
            payment_gateway="RAZORPAY",
            status="PENDING",
        )

        return JsonResponse(
            {
                "success": True,
                "order_id": razorpay_order["id"],
                "amount": amount_in_paisa,
                "currency": "INR",
                "key": settings.RAZORPAY_API_KEY,
            }
        )

    except razorpay.errors.BadRequestError as e:
        return JsonResponse({"success": False, "error": f"Razorpay error: {e}"}, status=502)

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ===========================================================================
# VERIFY PAYMENT  —  POST /api/payments/verify-payment/
#
# FIX: Returns JSON only — never redirects. The frontend JS handles the
# success/failure UI entirely within the modal.
# ===========================================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def verify_payment(request):
    try:
        razorpay_order_id   = request.data.get("razorpay_order_id")
        razorpay_payment_id = request.data.get("razorpay_payment_id")
        razorpay_signature  = request.data.get("razorpay_signature")

        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
            return JsonResponse({"error": "Missing payment details"}, status=400)

        payment_tx = get_object_or_404(
            PaymentTransaction,
            razorpay_order_id=razorpay_order_id,
            user=request.user,
        )

        # Guard against duplicate verification
        if payment_tx.status == "SUCCESS":
            return JsonResponse({"success": True, "message": "Payment already verified"})

        # Signature verification (raises SignatureVerificationError on failure)
        razorpay_client.utility.verify_payment_signature(
            {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            }
        )

        with transaction.atomic():
            # Fetch full payment details from Razorpay
            payment_details = razorpay_client.payment.fetch(razorpay_payment_id)

            payment_tx.status               = "SUCCESS"
            payment_tx.razorpay_payment_id  = razorpay_payment_id
            payment_tx.razorpay_signature   = razorpay_signature
            payment_tx.paid_at              = timezone.now()
            payment_tx.payment_mode         = payment_details.get("method")
            payment_tx.gateway_response     = payment_details

            card = payment_details.get("card")
            if card:
                payment_tx.card_network = card.get("network")
                payment_tx.card_number  = f"XXXX XXXX XXXX {card.get('last4', '****')}"

            payment_tx.save()

            # Credit update
            now = timezone.now()
            validity = timedelta(days=payment_tx.plan.validity_days)

            user_credit, created = UserCredit.objects.get_or_create(
                user=request.user,
                defaults={
                    "balance":    payment_tx.credits,
                    "expires_at": now + validity,
                },
            )

            if not created:
                user_credit.balance += payment_tx.credits
                # Extend expiry: if already expired → start fresh from now
                base = max(user_credit.expires_at, now)
                user_credit.expires_at = base + validity
                user_credit.save()

        # FIX: Return the new credit balance so the frontend can update
        # the live counter without a page reload.
        return JsonResponse({
            "success": True,
            "message": "Payment verified and credits added",
            "new_balance": user_credit.balance,
            "credits_added": payment_tx.credits,
        })

    except razorpay.errors.SignatureVerificationError:
        try:
            PaymentTransaction.objects.filter(
                razorpay_order_id=razorpay_order_id,
                user=request.user,
            ).update(status="FAILED", failure_reason="Signature verification failed")
        except Exception:
            pass

        return JsonResponse({"success": False, "error": "Invalid payment signature"}, status=400)

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ===========================================================================
# REFUND PAYMENT  —  POST /api/payments/refund-payment/
# ===========================================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def refund_captured_payment_rest(request):
    try:
        payment_id = request.data.get("payment_id")

        if not payment_id:
            return JsonResponse({"error": "payment_id is required"}, status=400)

        payment_tx = get_object_or_404(
            PaymentTransaction,
            razorpay_payment_id=payment_id,
            user=request.user,
        )

        if payment_tx.status == "REFUNDED":
            return JsonResponse({"success": True, "message": "Already refunded"})

        if payment_tx.status != "SUCCESS":
            return JsonResponse(
                {"error": "Only successful payments can be refunded"},
                status=400,
            )

        refund = razorpay_client.payment.refund(payment_id)

        with transaction.atomic():
            payment_tx.status           = "REFUNDED"
            payment_tx.gateway_response = refund
            payment_tx.save()

            try:
                user_credit = UserCredit.objects.get(user=request.user)
                user_credit.balance = max(0, user_credit.balance - payment_tx.credits)
                user_credit.save()
            except UserCredit.DoesNotExist:
                pass

        return JsonResponse({"success": True, "message": "Refund processed", "refund": refund})

    except razorpay.errors.BadRequestError as e:
        return JsonResponse({"success": False, "error": f"Razorpay error: {e}"}, status=502)

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)



# ===========================================================================
# PAYMENT CALLBACK  —  GET /api/payments/payment-callback/
#
# Razorpay redirects here for redirect-based payment methods (Netbanking,
# some UPI apps, certain wallets) that cannot complete inside the JS popup.
#
# Razorpay sends these GET params:
#   razorpay_payment_id, razorpay_payment_link_id,
#   razorpay_payment_link_reference_id,
#   razorpay_payment_link_status,
#   razorpay_signature
#
# For standard orders (not payment links) it sends:
#   razorpay_order_id, razorpay_payment_id, razorpay_signature
#
# We verify, credit the user, and render a result page —
# NEVER return JSON here because the browser landed on this URL directly.
# ===========================================================================

@csrf_exempt   # Razorpay's redirect POST/GET does not include Django's CSRF token
def payment_callback(request):
    """
    Handles the redirect-back from Razorpay for redirect-based payment
    methods (Netbanking, some UPI apps). Verifies the signature, credits
    the user, and renders payment_result.html.

    This view is intentionally NOT wrapped in @login_required because
    Razorpay's redirect may not preserve the session cookie on some
    browsers/payment flows. We authenticate via the order ID instead.
    """
    # Razorpay sends params as GET for older flows, POST for newer ones — handle both
    params = request.POST if request.method == "POST" else request.GET

    razorpay_order_id   = params.get("razorpay_order_id")
    razorpay_payment_id = params.get("razorpay_payment_id")
    razorpay_signature  = params.get("razorpay_signature")

    # ── Missing params → generic error page ──
    if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
        return render(request, "payments/payment_result.html", {
            "success": False,
            "message": "Invalid callback — missing payment parameters.",
            "redirect_url": "/",
        })

    # ── Look up the transaction (no user filter — session may be gone) ──
    try:
        payment_tx = PaymentTransaction.objects.select_related(
            "user", "plan"
        ).get(razorpay_order_id=razorpay_order_id)
    except PaymentTransaction.DoesNotExist:
        return render(request, "payments/payment_result.html", {
            "success": False,
            "message": "Payment record not found. Please contact support.",
            "redirect_url": "/",
        })

    # ── Already verified (user refreshed the callback URL) ──
    if payment_tx.status == "SUCCESS":
        return render(request, "payments/payment_result.html", {
            "success": True,
            "message": "Payment already verified.",
            "credits_added": payment_tx.credits,
            "plan_name": payment_tx.plan.name if payment_tx.plan else "",
            "redirect_url": "/",
        })

    # ── Signature verification ──
    try:
        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id":  razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature,
        })
    except razorpay.errors.SignatureVerificationError:
        PaymentTransaction.objects.filter(
            razorpay_order_id=razorpay_order_id
        ).update(status="FAILED", failure_reason="Signature verification failed (callback)")

        return render(request, "payments/payment_result.html", {
            "success": False,
            "message": "Payment signature verification failed. If money was debited, please contact support.",
            "redirect_url": "/",
        })

    # ── Credit user ──
    try:
        with transaction.atomic():
            payment_details = razorpay_client.payment.fetch(razorpay_payment_id)

            payment_tx.status              = "SUCCESS"
            payment_tx.razorpay_payment_id = razorpay_payment_id
            payment_tx.razorpay_signature  = razorpay_signature
            payment_tx.paid_at             = timezone.now()
            payment_tx.payment_mode        = payment_details.get("method")
            payment_tx.gateway_response    = payment_details

            card = payment_details.get("card")
            if card:
                payment_tx.card_network = card.get("network")
                payment_tx.card_number  = f"XXXX XXXX XXXX {card.get('last4', '****')}"

            payment_tx.save()

            now      = timezone.now()
            validity = timedelta(days=payment_tx.plan.validity_days)

            user_credit, created = UserCredit.objects.get_or_create(
                user=payment_tx.user,
                defaults={
                    "balance":    payment_tx.credits,
                    "expires_at": now + validity,
                },
            )

            if not created:
                user_credit.balance   += payment_tx.credits
                base = max(user_credit.expires_at, now)
                user_credit.expires_at = base + validity
                user_credit.save()

    except Exception as e:
        return render(request, "payments/payment_result.html", {
            "success": False,
            "message": f"Payment was received but crediting failed: {e}. Please contact support with order ID: {razorpay_order_id}",
            "redirect_url": "/",
        })

    return render(request, "payments/payment_result.html", {
        "success": True,
        "message": "Payment successful! Credits have been added to your account.",
        "credits_added": payment_tx.credits,
        "plan_name": payment_tx.plan.name if payment_tx.plan else "",
        "new_balance": user_credit.balance,
        "redirect_url": "/",
    })



def payment_page(request):
    plans = CreditPlan.objects.filter(is_active=True).order_by("display_order")
    return render(
        request,
        "payments/payment_page.html",
        {
            "credit_plans": plans,
            "razorpay_key": settings.RAZORPAY_API_KEY,
        },
    )


# ===========================================================================
# PAYMENT HISTORY  —  GET /api/payments/payment-history/
# ===========================================================================

class PaymentTransactionFilter(django_filters.FilterSet):

    created_from = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_to = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )
    amount_min = django_filters.NumberFilter(
        field_name="amount", lookup_expr="gte"
    )
    amount_max = django_filters.NumberFilter(
        field_name="amount", lookup_expr="lte"
    )

    class Meta:
        model  = PaymentTransaction
        fields = {
            "status":           ["exact"],
            "transaction_type": ["exact"],
        }


class PaymentHistory(generics.ListAPIView):

    serializer_class    = PaymentTransactionSerializer
    permission_classes  = [IsAuthenticated]
    filter_backends     = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class     = PaymentTransactionFilter
    ordering_fields     = ["created_at", "amount"]
    ordering            = ["-created_at"]

    def get_queryset(self):
        return PaymentTransaction.objects.filter(user=self.request.user)