import json
import razorpay

from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse

from django.views.decorators.http import (
    require_http_methods
)

from django.views.decorators.csrf import (
    csrf_protect
)

from django.contrib.admin.views.decorators import (
    staff_member_required
)

from payments.models import PaymentTransaction


# Razorpay Client
razorpay_client = razorpay.Client(
    auth=(
        settings.RAZORPAY_API_KEY,
        settings.RAZORPAY_API_SECRET_KEY
    )
)


@staff_member_required
def refund_admin_view(request):

    context = {
        "title": "Process Refund"
    }

    if "booking_id" in request.GET:
        context["prefill_booking_id"] = (
            request.GET["booking_id"]
        )

    return render(
        request,
        "refund_admin.html",
        context
    )


@staff_member_required
@require_http_methods(["POST"])
@csrf_protect
def process_refund_ajax(request):

    try:

        data = json.loads(request.body)

        booking_id = data.get("booking_id")

        refund_type = data.get(
            "refund_type",
            "normal"
        )

        amount_type = data.get(
            "amount_type",
            "full"
        )

        refund_amount = data.get(
            "refund_amount"
        )

        reason = data.get("reason", "")

        notes = data.get("notes", "")

        if not booking_id:

            return JsonResponse({
                "success": False,
                "error": "booking_id is required"
            }, status=400)

        # Find transaction
        # Using razorpay_order_id as booking_id
        transaction = PaymentTransaction.objects.filter(
            razorpay_order_id=booking_id
        ).first()

        # fallback search
        if not transaction:

            transaction = PaymentTransaction.objects.filter(
                razorpay_payment_id=booking_id
            ).first()

        if not transaction:

            return JsonResponse({
                "success": False,
                "error": "Transaction not found"
            }, status=404)

        if transaction.status == "REFUNDED":

            return JsonResponse({
                "success": False,
                "error": "Payment already refunded"
            }, status=400)

        if not transaction.razorpay_payment_id:

            return JsonResponse({
                "success": False,
                "error": "Payment ID missing"
            }, status=400)

        # Determine refund amount
        refund_payload = {}

        if amount_type == "partial":

            if not refund_amount:

                return JsonResponse({
                    "success": False,
                    "error": "Refund amount required"
                }, status=400)

            refund_amount_paisa = int(
                float(refund_amount) * 100
            )

            refund_payload["amount"] = (
                refund_amount_paisa
            )

        # Add notes
        if notes:
            refund_payload["notes"] = {
                "reason": reason,
                "admin_notes": notes,
                "refund_type": refund_type
            }

        # Speed option
        if refund_type == "instant":
            refund_payload["speed"] = "optimum"

        # Razorpay Refund API
        refund_response = razorpay_client.payment.refund(
            transaction.razorpay_payment_id,
            refund_payload
        )

        # Update transaction
        transaction.status = "REFUNDED"

        transaction.gateway_response = {
            "refund_response": refund_response
        }

        transaction.failure_reason = None

        transaction.save()

        # Return frontend-compatible response
        return JsonResponse({

            "success": True,

            "message": "Refund initiated successfully",

            "data": {

                "booking_id": booking_id,

                "refund_amount": (
                    refund_amount
                    if amount_type == "partial"
                    else str(transaction.amount)
                ),

                "refund_type": refund_type,

                "refund_id": refund_response.get("id"),

                "status": refund_response.get(
                    "status",
                    "processed"
                ),

                "estimated_time": (
                    "5-7 minutes"
                    if refund_type == "instant"
                    else "5-7 business days"
                ),

                "gateway": "Razorpay"
            }

        })

    except razorpay.errors.BadRequestError as e:

        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=400)

    except Exception as e:

        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)