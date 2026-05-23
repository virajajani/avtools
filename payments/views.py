import razorpay
from datetime import timedelta

from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import generics, filters

from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as django_filters

from .models import CreditPlan, PaymentTransaction
from .serializers import (
    CreditPlanSerializer,
    PaymentTransactionSerializer,
)
from django.core.paginator import Paginator
from accounts.models import UserCredit, CreditHistory
from django.db.models import Sum
from django.contrib.auth.decorators import login_required

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
# CREDIT PLANS
# ===========================================================================

@api_view(["GET"])
@permission_classes([AllowAny])
def get_credit_plans(request):
    plans = CreditPlan.objects.filter(is_active=True).order_by("display_order")
    serializer = CreditPlanSerializer(plans, many=True)
    return Response(serializer.data)


# ===========================================================================
# CREATE ORDER
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

        if plan.offer_percent > 0:
            discount    = (plan.price * plan.offer_percent) / 100
            final_price = plan.price - discount
        else:
            final_price = plan.price

        amount_in_paisa = int(final_price * 100)

        razorpay_order = razorpay_client.order.create({
            "amount":          amount_in_paisa,
            "currency":        "INR",
            "payment_capture": 1,
        })

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

        return JsonResponse({
            "success":  True,
            "order_id": razorpay_order["id"],
            "amount":   amount_in_paisa,
            "currency": "INR",
            "key":      settings.RAZORPAY_API_KEY,
        })

    except razorpay.errors.BadRequestError as e:
        return JsonResponse({"success": False, "error": f"Razorpay error: {e}"}, status=502)

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ===========================================================================
# VERIFY PAYMENT
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

        if payment_tx.status == "SUCCESS":
            return JsonResponse({"success": True, "message": "Payment already verified"})

        # ── Verify signature ──────────────────────────────────────────────────
        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id":   razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature":  razorpay_signature,
        })

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

            # ── Credit user ───────────────────────────────────────────────────
            _now     = timezone.now()
            validity = timedelta(days=payment_tx.plan.validity_days)

            user_credit, created = UserCredit.objects.get_or_create(
                user=request.user,
                defaults={
                    "balance":    payment_tx.credits,
                    "expires_at": _now + validity,
                },
            )

            if created:
                previous_balance = 0
                # balance already set via defaults above
            else:
                previous_balance       = user_credit.balance
                user_credit.balance   += payment_tx.credits
                base                   = max(user_credit.expires_at, _now)
                user_credit.expires_at = base + validity
                user_credit.save()

            # ── Record credit history ─────────────────────────────────────────
            CreditHistory.objects.create(
                user=request.user,
                credits=payment_tx.credits,
                transaction_type="ADD",
                previous_balance=previous_balance,
                current_balance=user_credit.balance,
                description=f"Purchased {payment_tx.plan.name}",
                payment_id=razorpay_payment_id,
            )

        return JsonResponse({
            "success":       True,
            "message":       "Payment verified and credits added",
            "new_balance":   user_credit.balance,
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
# REFUND PAYMENT
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
                {"error": "Only successful payments can be refunded"}, status=400
            )

        refund = razorpay_client.payment.refund(payment_id)

        with transaction.atomic():
            payment_tx.status           = "REFUNDED"
            payment_tx.gateway_response = refund
            payment_tx.save()

            try:
                user_credit      = UserCredit.objects.get(user=request.user)
                old_balance      = user_credit.balance
                user_credit.balance = max(0, user_credit.balance - payment_tx.credits)
                user_credit.save()

                CreditHistory.objects.create(
                    user=request.user,
                    credits=payment_tx.credits,
                    transaction_type="REFUND",
                    previous_balance=old_balance,
                    current_balance=user_credit.balance,
                    description="Refund processed",
                    payment_id=payment_id,
                )
            except UserCredit.DoesNotExist:
                pass

        return JsonResponse({
            "success": True,
            "message": "Refund processed",
            "refund":  refund,
        })

    except razorpay.errors.BadRequestError as e:
        return JsonResponse({"success": False, "error": f"Razorpay error: {e}"}, status=502)

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ===========================================================================
# PAYMENT CALLBACK
# ===========================================================================

@csrf_exempt
def payment_callback(request):
    """
    Handles redirect-back from Razorpay for redirect-based payment methods
    (Netbanking, some UPI apps). Verifies signature, credits the user,
    and renders payment_result.html.
    """
    params = request.POST if request.method == "POST" else request.GET

    razorpay_order_id   = params.get("razorpay_order_id")
    razorpay_payment_id = params.get("razorpay_payment_id")
    razorpay_signature  = params.get("razorpay_signature")

    if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
        return render(request, "payments/payment_result.html", {
            "success":      False,
            "message":      "Invalid callback — missing payment parameters.",
            "redirect_url": "/",
        })

    try:
        payment_tx = PaymentTransaction.objects.select_related(
            "user", "plan"
        ).get(razorpay_order_id=razorpay_order_id)
    except PaymentTransaction.DoesNotExist:
        return render(request, "payments/payment_result.html", {
            "success":      False,
            "message":      "Payment record not found. Please contact support.",
            "redirect_url": "/",
        })

    if payment_tx.status == "SUCCESS":
        return render(request, "payments/payment_result.html", {
            "success":       True,
            "message":       "Payment already verified.",
            "credits_added": payment_tx.credits,
            "plan_name":     payment_tx.plan.name if payment_tx.plan else "",
            "redirect_url":  "/",
        })

    # ── Verify signature ──────────────────────────────────────────────────────
    try:
        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id":   razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature":  razorpay_signature,
        })
    except razorpay.errors.SignatureVerificationError:
        PaymentTransaction.objects.filter(
            razorpay_order_id=razorpay_order_id
        ).update(status="FAILED", failure_reason="Signature verification failed (callback)")

        return render(request, "payments/payment_result.html", {
            "success":      False,
            "message":      "Payment signature verification failed. If money was debited, please contact support.",
            "redirect_url": "/",
        })

    # ── Credit user ───────────────────────────────────────────────────────────
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

            _now     = timezone.now()
            validity = timedelta(days=payment_tx.plan.validity_days)

            user_credit, created = UserCredit.objects.get_or_create(
                user=payment_tx.user,
                defaults={
                    "balance":    payment_tx.credits,
                    "expires_at": _now + validity,
                },
            )

            if created:
                previous_balance = 0
            else:
                previous_balance       = user_credit.balance
                user_credit.balance   += payment_tx.credits
                base                   = max(user_credit.expires_at, _now)
                user_credit.expires_at = base + validity
                user_credit.save()

            CreditHistory.objects.create(
                user=payment_tx.user,
                credits=payment_tx.credits,
                transaction_type="ADD",
                previous_balance=previous_balance,
                current_balance=user_credit.balance,
                description=f"Purchased {payment_tx.plan.name} (callback)",
                payment_id=razorpay_payment_id,
            )

    except Exception as e:
        return render(request, "payments/payment_result.html", {
            "success":      False,
            "message":      f"Payment was received but crediting failed: {e}. Please contact support with order ID: {razorpay_order_id}",
            "redirect_url": "/",
        })

    return render(request, "payments/payment_result.html", {
        "success":       True,
        "message":       "Payment successful! Credits have been added to your account.",
        "credits_added": payment_tx.credits,
        "plan_name":     payment_tx.plan.name if payment_tx.plan else "",
        "new_balance":   user_credit.balance,
        "redirect_url":  "/",
    })


# ===========================================================================
# PAYMENT PAGE
# ===========================================================================

def payment_page(request):
    plans = CreditPlan.objects.filter(is_active=True).order_by("display_order")
    return render(request, "payments/payment_page.html", {
        "credit_plans":  plans,
        "razorpay_key":  settings.RAZORPAY_API_KEY,
    })



# ===========================================================================
# PURCHASE HISTORY  —  GET /payments/purchase-history/
# Full HTML page showing transaction history + credit expiry info.
# ===========================================================================
 
@login_required
def purchase_history(request):
    status_filter = request.GET.get("status", "")
    plan_filter   = request.GET.get("plan", "")
 
    qs = PaymentTransaction.objects.filter(
        user=request.user
    ).select_related("plan").order_by("-created_at")
 
    if status_filter:
        qs = qs.filter(status=status_filter)
    if plan_filter:
        qs = qs.filter(plan__name=plan_filter)
 
    # Aggregate stats (over ALL transactions, ignoring the current filter)
    all_tx = PaymentTransaction.objects.filter(user=request.user)
    total_spent     = all_tx.filter(status="SUCCESS").aggregate(
        t=Sum("amount")
    )["t"] or 0
    total_purchases = all_tx.filter(status="SUCCESS").count()
 
    # Credit info
    user_credit = UserCredit.objects.filter(user=request.user).first()
    now         = timezone.now()
    is_expired  = False
    days_left   = None
 
    if user_credit and user_credit.expires_at:
        is_expired = user_credit.expires_at < now
        if not is_expired:
            delta     = user_credit.expires_at - now
            days_left = delta.days
 
    # Paginate
    paginator = Paginator(qs, 15)
    page_num  = request.GET.get("page", 1)
    page_obj  = paginator.get_page(page_num)
 
    return render(request, "payments/purchase_history.html", {
        "page_obj":        page_obj,
        "user_credit":     user_credit,
        "total_spent":     total_spent,
        "total_purchases": total_purchases,
        "is_expired":      is_expired,
        "days_left":       days_left,
        "status_filter":   status_filter,
        "plan_filter":     plan_filter,
    })
 
 

# ===========================================================================
# PAYMENT HISTORY
# ===========================================================================

class PaymentTransactionFilter(django_filters.FilterSet):
    created_from = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_to   = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    amount_min   = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    amount_max   = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")

    class Meta:
        model  = PaymentTransaction
        fields = {
            "status":           ["exact"],
            "transaction_type": ["exact"],
        }


class PaymentHistory(generics.ListAPIView):
    serializer_class   = PaymentTransactionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class    = PaymentTransactionFilter
    ordering_fields    = ["created_at", "amount"]
    ordering           = ["-created_at"]

    def get_queryset(self):
        return PaymentTransaction.objects.filter(user=self.request.user)