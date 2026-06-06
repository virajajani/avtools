from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework.authtoken.models import Token

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import User, UserDevice, DeviceRegistration, ProductReview
from .serializers import RegisterSerializer, LoginSerializer
from .utils import token_expiry_time
import random
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.conf import settings

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from .models import ContactSupport, UserCredit, CreditHistory
from datetime import timedelta


# ═══════════════════════════════════════════════
# REGISTER API — with device block
# ═══════════════════════════════════════════════

@method_decorator(csrf_exempt, name='dispatch')
class RegisterAPI(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        print(f"📥 Received data: {request.data}")

        # ── Device fingerprint check ──────────────────────────────────
        fingerprint = request.data.get("device_fingerprint", "").strip()
        ip          = request.META.get("REMOTE_ADDR")
        ua          = request.META.get("HTTP_USER_AGENT", "")

        if fingerprint:
            if DeviceRegistration.objects.filter(device_fingerprint=fingerprint).exists():
                return Response(
                    {"error": "An account is already registered on this device. Please log in instead."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # ── Validate serializer ───────────────────────────────────────
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            print(f"❌ Validation errors: {serializer.errors}")
            return Response(
                {"error": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── Create user ───────────────────────────────────────────────
        user = serializer.save()
        user.is_email_verified = True
        user.save()

        # ── Create auth token ─────────────────────────────────────────
        token, _ = Token.objects.get_or_create(user=user)

        # ── Save device_id (mobile app) ───────────────────────────────
        device_id = request.data.get("device_id")
        if device_id:
            UserDevice.objects.update_or_create(
                user=user,
                device_id=device_id,
                defaults={
                    "token_expiry": token_expiry_time(),
                    "last_login":   timezone.now()
                }
            )

        # ── Save device fingerprint (web browser) ─────────────────────
        if fingerprint:
            DeviceRegistration.objects.get_or_create(
                device_fingerprint=fingerprint,
                defaults={
                    "user":       user,
                    "ip_address": ip,
                    "user_agent": ua,
                }
            )

        # ── Give 10 free credits (get_or_create prevents duplicate) ───
        credit, created = UserCredit.objects.get_or_create(
            user=user,
            defaults={
                "balance":    10,
                "expires_at": timezone.now() + timedelta(days=365),
            }
        )

        # Only log credit history if we actually created a new row
        if created:
            CreditHistory.objects.create(
                user=user,
                credits=10,
                transaction_type="ADD",
                previous_balance=0,
                current_balance=10,
                description="Welcome bonus — 10 free credits",
            )
        else:
            print(f"⚠️ UserCredit already existed for {user.email} with balance {credit.balance}")

        return Response({
            "message":    "Account created successfully!",
            "token":      token.key,
            "expires_at": token_expiry_time(),
            "user": {
                "email":      user.email,
                "first_name": user.first_name,
                "last_name":  user.last_name
            }
        }, status=status.HTTP_201_CREATED)


# ═══════════════════════════════════════════════
# LOGIN API
# ═══════════════════════════════════════════════

@method_decorator(csrf_exempt, name="dispatch")
class LoginAPI(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"]
        )

        if not user:
            return Response({"error": "Invalid credentials"}, status=400)

        token, _ = Token.objects.get_or_create(user=user)

        UserDevice.objects.update_or_create(
            user=user,
            device_id=serializer.validated_data["device_id"],
            defaults={
                "token_expiry": token_expiry_time(),
                "last_login":   timezone.now()
            }
        )

        user.last_login = timezone.now()
        user.save()

        return Response({
            "token":      token.key,
            "expires_at": token_expiry_time(),
            "user": {
                "email":      user.email,
                "first_name": user.first_name,
                "last_name":  user.last_name
            }
        })


# ═══════════════════════════════════════════════
# FORGOT PASSWORD / OTP / RESET
# ═══════════════════════════════════════════════

@method_decorator(csrf_exempt, name="dispatch")
class ForgotPasswordAPI(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        if not email:
            return Response(
                {"message": "Email is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response(
                {"message": "Email not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        otp = str(random.randint(100000, 999999))
        request.session["reset_email"] = user.email
        request.session["reset_otp"]   = otp

        send_mail(
            subject="AVTools Password Reset OTP",
            message=f"Your OTP is: {otp}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False
        )

        return Response(
            {"message": "OTP sent successfully"},
            status=status.HTTP_200_OK
        )


@method_decorator(csrf_exempt, name="dispatch")
class VerifyOTPAPI(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        otp   = request.data.get("otp", "").strip()

        if request.session.get("reset_email") != email:
            return Response(
                {"message": "Invalid email"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if request.session.get("reset_otp") != otp:
            return Response(
                {"message": "Invalid OTP"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({"message": "OTP verified"}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class ResetPasswordAPI(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        email    = request.data.get("email", "").strip().lower()
        password = request.data.get("password", "").strip()

        if not password:
            return Response(
                {"message": "Password is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response(
                {"message": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        user.password = make_password(password)
        user.save()

        request.session.pop("reset_email", None)
        request.session.pop("reset_otp",   None)

        return Response(
            {"message": "Password reset successful"},
            status=status.HTTP_200_OK
        )


# ═══════════════════════════════════════════════
# CONTACT SUPPORT
# ═══════════════════════════════════════════════

def contact_support(request):
    if request.method == "POST":
        ContactSupport.objects.create(
            first_name    = request.POST.get("first_name"),
            last_name     = request.POST.get("last_name"),
            mobile_number = request.POST.get("mobile"),
            email         = request.POST.get("email"),
            message       = request.POST.get("message"),
        )
        return render(request, "user/contact_success.html")
    return render(request, "user/contact.html")


# ═══════════════════════════════════════════════
# DEVICE CHECK API
# ═══════════════════════════════════════════════

def check_device(request):
    """AJAX — returns whether this browser fingerprint is already registered."""
    fingerprint = request.GET.get("fingerprint", "").strip()
    if not fingerprint:
        return JsonResponse({"registered": False})
    exists = DeviceRegistration.objects.filter(
        device_fingerprint=fingerprint
    ).exists()
    return JsonResponse({"registered": exists})


# ═══════════════════════════════════════════════
# REVIEW APIs
# ═══════════════════════════════════════════════

@login_required(login_url='generator:signin')
@require_POST
def submit_review(request):
    rating  = request.POST.get("rating")
    comment = request.POST.get("comment", "").strip()

    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse(
            {"error": "Rating must be between 1 and 5."},
            status=400
        )

    if not comment:
        return JsonResponse({"error": "Please write a comment."}, status=400)

    review, created = ProductReview.objects.update_or_create(
        user=request.user,
        defaults={
            "rating":  rating,
            "comment": comment,
        }
    )

    return JsonResponse({
        "success": True,
        "message": "Review submitted!" if created else "Review updated!",
        "review": {
            "rating":     review.rating,
            "comment":    review.comment,
            "created_at": review.created_at.strftime("%d %b %Y"),
        }
    })


def get_reviews(request):
    """Public — returns all visible reviews."""
    reviews = ProductReview.objects.filter(
        is_visible=True
    ).select_related("user")

    data = [
        {
            "user":       r.user.get_full_name() or r.user.username,
            "rating":     r.rating,
            "comment":    r.comment,
            "created_at": r.created_at.strftime("%d %b %Y"),
        }
        for r in reviews
    ]
    return JsonResponse({"reviews": data})