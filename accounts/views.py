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

from firebase_admin import auth as firebase_auth
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.authtoken.models import Token
from django.utils import timezone
from datetime import timedelta
from accounts.models import DeviceRegistration, UserDevice




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
                "expires_at": timezone.now() + timedelta(days=30),
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

        # ── Send welcome email (non-blocking failure) ──────────────────
        send_welcome_email(user, credits=credit.balance)

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

        # ── Beautiful HTML email ──────────────────────────────────────
        first_name   = user.first_name or user.email.split("@")[0]
        html_message = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Password Reset OTP</title>
</head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:'Inter',Arial,sans-serif;">

  <!-- Wrapper -->
  <table width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background-color:#f1f5f9;padding:40px 20px;">
    <tr>
      <td align="center">

        <!-- Card -->
        <table width="560" cellpadding="0" cellspacing="0" border="0"
               style="max-width:560px;width:100%;background:#ffffff;
                      border-radius:24px;overflow:hidden;
                      box-shadow:0 20px 60px rgba(15,23,42,0.10);">

          <!-- ── HEADER GRADIENT ── -->
          <tr>
            <td style="background:linear-gradient(135deg,#3b82f6 0%,#8b5cf6 100%);
                       padding:36px 40px;text-align:center;">

              <!-- Logo placeholder — replace src with your hosted logo -->
              <div style="font-size:28px;font-weight:900;color:#ffffff;
                          letter-spacing:-0.5px;margin-bottom:6px;">
                ⚡ AVTools
              </div>
              <div style="font-size:13px;color:rgba(255,255,255,0.80);
                          font-weight:500;">
                Empowering Your Vision
              </div>
            </td>
          </tr>

          <!-- ── BODY ── -->
          <tr>
            <td style="padding:40px 40px 32px;">

              <!-- Icon -->
              <div style="text-align:center;margin-bottom:24px;">
                <div style="display:inline-block;width:72px;height:72px;
                            background:linear-gradient(135deg,#eff6ff,#f5f3ff);
                            border-radius:50%;line-height:72px;font-size:32px;
                            border:2px solid #e0e7ff;">
                  🔐
                </div>
              </div>

              <!-- Greeting -->
              <h1 style="margin:0 0 8px;font-size:22px;font-weight:800;
                         color:#0f172a;text-align:center;letter-spacing:-0.3px;">
                Password Reset Request
              </h1>
              <p style="margin:0 0 28px;font-size:15px;color:#64748b;
                        text-align:center;line-height:1.6;">
                Hi <strong style="color:#0f172a;">{first_name}</strong>, we received a request
                to reset your AVTools password. Use the code below.
              </p>

              <!-- OTP Box -->
              <div style="background:linear-gradient(135deg,#f8fafc,#f1f5f9);
                          border:2px dashed #c7d2fe;border-radius:16px;
                          padding:28px 24px;text-align:center;margin-bottom:28px;">
                <p style="margin:0 0 10px;font-size:12px;font-weight:700;
                           color:#6366f1;text-transform:uppercase;
                           letter-spacing:0.1em;">
                  Your Verification Code
                </p>

                <!-- OTP Digits -->
                <div style="display:inline-block;">
                  {''.join([
                    f'<span style="display:inline-block;width:44px;height:52px;'
                    f'background:#ffffff;border:2px solid #e0e7ff;'
                    f'border-radius:10px;font-size:26px;font-weight:900;'
                    f'color:#2563eb;line-height:52px;text-align:center;'
                    f'margin:0 3px;box-shadow:0 2px 8px rgba(99,102,241,0.12);">'
                    f'{digit}</span>'
                    for digit in otp
                  ])}
                </div>

                <p style="margin:14px 0 0;font-size:12px;color:#94a3b8;
                           font-weight:500;">
                  ⏰ This code expires in <strong style="color:#ef4444;">10 minutes</strong>
                </p>
              </div>

              <!-- Warning -->
              <div style="background:#fff7ed;border:1px solid #fed7aa;
                          border-radius:12px;padding:14px 18px;
                          margin-bottom:28px;">
                <p style="margin:0;font-size:13px;color:#92400e;
                           line-height:1.6;">
                  🔒 <strong>Security notice:</strong> If you did not request
                  this code, please ignore this email. Your account remains
                  secure. Do not share this code with anyone.
                </p>
              </div>

              <!-- Steps -->
              <p style="margin:0 0 12px;font-size:13px;font-weight:700;
                         color:#334155;">
                How to reset your password:
              </p>
              <table cellpadding="0" cellspacing="0" border="0" width="100%">
                <tr>
                  <td style="padding:6px 0;">
                    <span style="display:inline-block;width:22px;height:22px;
                                 background:#eff6ff;border-radius:50%;
                                 font-size:11px;font-weight:800;color:#2563eb;
                                 text-align:center;line-height:22px;
                                 margin-right:10px;vertical-align:middle;">1</span>
                    <span style="font-size:13px;color:#475569;vertical-align:middle;">
                      Go back to the AVTools password reset page
                    </span>
                  </td>
                </tr>
                <tr>
                  <td style="padding:6px 0;">
                    <span style="display:inline-block;width:22px;height:22px;
                                 background:#eff6ff;border-radius:50%;
                                 font-size:11px;font-weight:800;color:#2563eb;
                                 text-align:center;line-height:22px;
                                 margin-right:10px;vertical-align:middle;">2</span>
                    <span style="font-size:13px;color:#475569;vertical-align:middle;">
                      Enter the 6-digit code shown above
                    </span>
                  </td>
                </tr>
                <tr>
                  <td style="padding:6px 0;">
                    <span style="display:inline-block;width:22px;height:22px;
                                 background:#eff6ff;border-radius:50%;
                                 font-size:11px;font-weight:800;color:#2563eb;
                                 text-align:center;line-height:22px;
                                 margin-right:10px;vertical-align:middle;">3</span>
                    <span style="font-size:13px;color:#475569;vertical-align:middle;">
                      Create your new secure password
                    </span>
                  </td>
                </tr>
              </table>

            </td>
          </tr>

          <!-- ── DIVIDER ── -->
          <tr>
            <td style="padding:0 40px;">
              <div style="height:1px;background:#e2e8f0;"></div>
            </td>
          </tr>

          <!-- ── FOOTER ── -->
          <tr>
            <td style="padding:24px 40px 32px;text-align:center;">
              <p style="margin:0 0 8px;font-size:12px;color:#94a3b8;
                         line-height:1.6;">
                This email was sent to
                <strong style="color:#64748b;">{email}</strong>
                because a password reset was requested for your AVTools account.
              </p>
              <p style="margin:0 0 16px;font-size:12px;color:#94a3b8;">
                If you didn't request this, no action is needed.
              </p>

              <!-- Footer links -->
              <p style="margin:0 0 12px;">
                <a href="https://avtools.in"
                   style="color:#3b82f6;text-decoration:none;
                          font-size:12px;font-weight:600;margin:0 8px;">
                  avtools.in
                </a>
                <span style="color:#e2e8f0;">|</span>
                <a href="https://avtools.in/privacy/"
                   style="color:#3b82f6;text-decoration:none;
                          font-size:12px;font-weight:600;margin:0 8px;">
                  Privacy Policy
                </a>
                <span style="color:#e2e8f0;">|</span>
                <a href="https://avtools.in/contact/"
                   style="color:#3b82f6;text-decoration:none;
                          font-size:12px;font-weight:600;margin:0 8px;">
                  Support
                </a>
              </p>

              <p style="margin:0;font-size:11px;color:#cbd5e1;">
                © 2026 AVTools. All rights reserved.
              </p>
            </td>
          </tr>

        </table>
        <!-- /Card -->

      </td>
    </tr>
  </table>

</body>
</html>
        """

        # ── Plain text fallback ───────────────────────────────────────
        plain_message = (
            f"Hi {first_name},\n\n"
            f"Your AVTools password reset code is: {otp}\n\n"
            f"This code expires in 10 minutes.\n\n"
            f"If you did not request this, please ignore this email.\n\n"
            f"— AVTools Team"
        )

        # ── Send email ────────────────────────────────────────────────
        try:
            send_mail(
                subject     = "🔐 Your AVTools Password Reset Code",
                message     = plain_message,
                from_email  = settings.DEFAULT_FROM_EMAIL,
                recipient_list = [user.email],
                html_message   = html_message,
                fail_silently  = False,
            )
            print(f"✅ OTP email sent to {user.email}")
        except Exception as e:
            print(f"❌ Email send failed: {e}")
            return Response(
                {"message": "Failed to send email. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
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

        if not password or len(password) < 8:
            return Response(
                {"message": "Password must be at least 8 characters."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response(
                {"message": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # ✅ Use set_password() — never assign make_password() to .password manually.
        # This guarantees exactly one hashing pass regardless of any custom
        # save()/signal logic on the User model.
        user.set_password(password)
        user.save(update_fields=["password"])

        # Optional but recommended: invalidate any existing auth tokens so old
        # sessions/tokens can't be used with the stale credential state.
        Token.objects.filter(user=user).delete()

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

@method_decorator(csrf_exempt, name="dispatch")
class GoogleAuthAPI(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        id_token = request.data.get("id_token", "").strip()
        if not id_token:
            return Response({"error": "id_token is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            decoded = firebase_auth.verify_id_token(id_token)
        except Exception as e:
            print(f"❌ Firebase token verification failed: {e}")
            return Response({"error": "Invalid or expired Google token"}, status=status.HTTP_401_UNAUTHORIZED)

        email          = decoded.get("email")
        email_verified = decoded.get("email_verified", False)
        full_name      = decoded.get("name", "") or ""
        google_uid     = decoded.get("uid")
        picture_url    = decoded.get("picture")

        if not email:
            return Response({"error": "Google account has no email"}, status=status.HTTP_400_BAD_REQUEST)
        if not email_verified:
            return Response({"error": "Google email is not verified"}, status=status.HTTP_400_BAD_REQUEST)

        first_name, _, last_name = full_name.partition(" ")

        fingerprint = request.data.get("device_fingerprint", "").strip()
        ip = request.META.get("REMOTE_ADDR")
        ua = request.META.get("HTTP_USER_AGENT", "")

        # ── Look up by google_uid FIRST (authoritative), fall back to email ──
        user = User.objects.filter(google_uid=google_uid).first()
        if not user:
            user = User.objects.filter(email__iexact=email).first()

        is_new_user = user is None

        if fingerprint:
            existing_device = DeviceRegistration.objects.filter(
                device_fingerprint=fingerprint
            ).select_related("user").first()

            if existing_device and (is_new_user or existing_device.user_id != user.id):
                return Response(
                    {"error": "This device is already linked to a different AVTools account. Please log in with that account instead."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if is_new_user:
            user = User.objects.create(
                email=email,
                username=email,
                first_name=first_name,
                last_name=last_name,
                is_email_verified=True,
                auth_provider="GOOGLE",
                google_uid=google_uid,
                profile_picture_url=picture_url,
            )
            user.set_unusable_password()
            user.save()
        else:
            # Existing account (e.g. originally email/password) now also
            # linking Google — backfill the Google identity fields.
            update_fields = []
            if not user.is_email_verified:
                user.is_email_verified = True
                update_fields.append("is_email_verified")
            if not user.google_uid:
                user.google_uid = google_uid
                update_fields.append("google_uid")
            if picture_url and not user.profile_picture_url:
                user.profile_picture_url = picture_url
                update_fields.append("profile_picture_url")
            if update_fields:
                user.save(update_fields=update_fields)

        token, _ = Token.objects.get_or_create(user=user)

        device_id = request.data.get("device_id")
        if device_id:
            UserDevice.objects.update_or_create(
                user=user,
                device_id=device_id,
                defaults={"token_expiry": token_expiry_time(), "last_login": timezone.now()}
            )

        if fingerprint:
            DeviceRegistration.objects.get_or_create(
                device_fingerprint=fingerprint,
                defaults={"user": user, "ip_address": ip, "user_agent": ua},
            )

        if is_new_user:
            credit, created = UserCredit.objects.get_or_create(
                user=user,
                defaults={"balance": 10, "expires_at": timezone.now() + timedelta(days=30)},
            )
            if created:
                CreditHistory.objects.create(
                    user=user,
                    credits=10,
                    transaction_type="ADD",
                    previous_balance=0,
                    current_balance=10,
                    description="Welcome bonus — 10 free credits",
                )
            send_welcome_email(user, credits=credit.balance)

        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        return Response({
            "message":     "Account created successfully!" if is_new_user else "Login successful",
            "is_new_user": is_new_user,
            "token":       token.key,
            "expires_at":  token_expiry_time(),
            "user": {
                "email":      user.email,
                "first_name": user.first_name,
                "last_name":  user.last_name,
                "picture":    user.profile_picture_url,
            }
        }, status=status.HTTP_201_CREATED if is_new_user else status.HTTP_200_OK)
    

def send_welcome_email(user, credits=10):
    first_name = user.first_name or user.email.split("@")[0]

    html_message = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Welcome to AVTools</title>
</head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:'Inter',Arial,sans-serif;">

  <table width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background-color:#f1f5f9;padding:40px 20px;">
    <tr>
      <td align="center">

        <table width="580" cellpadding="0" cellspacing="0" border="0"
               style="max-width:580px;width:100%;background:#ffffff;
                      border-radius:24px;overflow:hidden;
                      box-shadow:0 20px 60px rgba(15,23,42,0.10);">

          <!-- ── HEADER ── -->
          <tr>
            <td style="background:linear-gradient(135deg,#3b82f6 0%,#8b5cf6 100%);
                       padding:40px;text-align:center;">
              <div style="font-size:28px;font-weight:900;color:#ffffff;
                          letter-spacing:-0.5px;margin-bottom:6px;">
                ⚡ AVTools
              </div>
              <div style="font-size:13px;color:rgba(255,255,255,0.80);font-weight:500;">
                The #1 Free Tool for Meesho Sellers
              </div>
            </td>
          </tr>

          <!-- ── BODY ── -->
          <tr>
            <td style="padding:40px 40px 24px;">

              <div style="text-align:center;margin-bottom:20px;">
                <div style="display:inline-block;width:72px;height:72px;
                            background:linear-gradient(135deg,#eff6ff,#f5f3ff);
                            border-radius:50%;line-height:72px;font-size:32px;
                            border:2px solid #e0e7ff;">
                  🎉
                </div>
              </div>

              <h1 style="margin:0 0 8px;font-size:22px;font-weight:800;
                         color:#0f172a;text-align:center;">
                Welcome aboard, {first_name}!
              </h1>
              <p style="margin:0 0 28px;font-size:15px;color:#64748b;
                        text-align:center;line-height:1.6;">
                You've joined 5,000+ Meesho sellers already saving time
                and money with AVTools. Here's what you get.
              </p>

              <!-- Credits box -->
              <div style="background:linear-gradient(135deg,#f8fafc,#f1f5f9);
                          border:2px dashed #c7d2fe;border-radius:16px;
                          padding:20px 24px;text-align:center;margin-bottom:28px;">
                <p style="margin:0 0 4px;font-size:12px;font-weight:700;
                           color:#6366f1;text-transform:uppercase;letter-spacing:0.1em;">
                  Welcome Bonus
                </p>
                <p style="margin:0;font-size:28px;font-weight:900;color:#2563eb;">
                  {credits} Free Image Credits
                </p>
                <p style="margin:6px 0 0;font-size:12px;color:#94a3b8;">
                  Valid for 1 Month — use them on the AI Image Generator anytime.
                </p>
              </div>

              <!-- Two tools -->
              <p style="margin:0 0 12px;font-size:13px;font-weight:700;color:#334155;">
                Your two tools, ready to use:
              </p>

              <div style="background:#f0fdfa;border:1px solid #99f6e4;border-radius:12px;
                          padding:16px 18px;margin-bottom:12px;">
                <p style="margin:0 0 4px;font-size:14px;font-weight:800;color:#0f766e;">
                  🏷️ Shipping Label Export — Always Free
                </p>
                <p style="margin:0;font-size:13px;color:#475569;line-height:1.6;">
                  Upload your Meesho invoice PDFs and get courier-wise,
                  product-wise sorted labels in seconds — ready for 3×5,
                  4×6, or A4 printing. No login needed, no cost, ever.
                </p>
              </div>

              <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:12px;
                          padding:16px 18px;margin-bottom:28px;">
                <p style="margin:0 0 4px;font-size:14px;font-weight:800;color:#1d4ed8;">
                  🖼️ AI Image Generator
                </p>
                <p style="margin:0;font-size:13px;color:#475569;line-height:1.6;">
                  Upload a product photo and our AI removes the background,
                  places it on a clean 2000×2000 canvas, and compresses it
                  to 150–300 KB — pushing your listing into a lower Meesho
                  shipping slab. Sellers typically save ₹25+ per order.
                </p>
              </div>

              <!-- How it works -->
              <p style="margin:0 0 12px;font-size:13px;font-weight:700;color:#334155;">
                Getting started takes under a minute:
              </p>
              <table cellpadding="0" cellspacing="0" border="0" width="100%">
                <tr>
                  <td style="padding:6px 0;">
                    <span style="display:inline-block;width:22px;height:22px;
                                 background:#eff6ff;border-radius:50%;font-size:11px;
                                 font-weight:800;color:#2563eb;text-align:center;
                                 line-height:22px;margin-right:10px;vertical-align:middle;">1</span>
                    <span style="font-size:13px;color:#475569;vertical-align:middle;">
                      Sign in and pick Label Export or Image Generator
                    </span>
                  </td>
                </tr>
                <tr>
                  <td style="padding:6px 0;">
                    <span style="display:inline-block;width:22px;height:22px;
                                 background:#eff6ff;border-radius:50%;font-size:11px;
                                 font-weight:800;color:#2563eb;text-align:center;
                                 line-height:22px;margin-right:10px;vertical-align:middle;">2</span>
                    <span style="font-size:13px;color:#475569;vertical-align:middle;">
                      Upload your Meesho invoice PDFs or product photo
                    </span>
                  </td>
                </tr>
                <tr>
                  <td style="padding:6px 0;">
                    <span style="display:inline-block;width:22px;height:22px;
                                 background:#eff6ff;border-radius:50%;font-size:11px;
                                 font-weight:800;color:#2563eb;text-align:center;
                                 line-height:22px;margin-right:10px;vertical-align:middle;">3</span>
                    <span style="font-size:13px;color:#475569;vertical-align:middle;">
                      Let AVTools sort your labels or optimize your image
                    </span>
                  </td>
                </tr>
                <tr>
                  <td style="padding:6px 0;">
                    <span style="display:inline-block;width:22px;height:22px;
                                 background:#eff6ff;border-radius:50%;font-size:11px;
                                 font-weight:800;color:#2563eb;text-align:center;
                                 line-height:22px;margin-right:10px;vertical-align:middle;">4</span>
                    <span style="font-size:13px;color:#475569;vertical-align:middle;">
                      Download instantly and start saving on every order
                    </span>
                  </td>
                </tr>
              </table>

              <!-- CTA -->
              <div style="text-align:center;margin:32px 0 8px;">
                <a href="https://avtools.in/label-cropper/"
                   style="display:inline-block;background:linear-gradient(135deg,#3b82f6,#8b5cf6);
                          color:#ffffff;text-decoration:none;font-size:14px;font-weight:700;
                          padding:14px 32px;border-radius:12px;
                          box-shadow:0 8px 20px rgba(99,102,241,0.25);">
                  🏷️ Export Your First Labels — Free →
                </a>
              </div>

            </td>
          </tr>

          <tr>
            <td style="padding:0 40px;">
              <div style="height:1px;background:#e2e8f0;"></div>
            </td>
          </tr>

          <!-- ── FOOTER ── -->
          <tr>
            <td style="padding:24px 40px 32px;text-align:center;">
              <p style="margin:0 0 8px;font-size:12px;color:#94a3b8;line-height:1.6;">
                This email was sent to
                <strong style="color:#64748b;">{user.email}</strong>
                because you created an AVTools account.
              </p>

              <p style="margin:0 0 12px;">
                <a href="https://avtools.in"
                   style="color:#3b82f6;text-decoration:none;font-size:12px;
                          font-weight:600;margin:0 8px;">avtools.in</a>
                <span style="color:#e2e8f0;">|</span>
                <a href="https://avtools.in/privacy/"
                   style="color:#3b82f6;text-decoration:none;font-size:12px;
                          font-weight:600;margin:0 8px;">Privacy Policy</a>
                <span style="color:#e2e8f0;">|</span>
                <a href="https://avtools.in/contact/"
                   style="color:#3b82f6;text-decoration:none;font-size:12px;
                          font-weight:600;margin:0 8px;">Support</a>
              </p>

              <p style="margin:0;font-size:11px;color:#cbd5e1;">
                © 2026 AVTools. All rights reserved.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>
    """

    plain_message = (
        f"Hi {first_name},\n\n"
        f"Welcome to AVTools — the free tool trusted by 5,000+ Meesho sellers!\n\n"
        f"You've received {credits} free image credits (valid for 1 Month).\n\n"
        f"Your two tools:\n"
        f"🏷️ Shipping Label Export — always free, no login. Upload Meesho "
        f"invoice PDFs and get courier-wise, sorted labels in seconds.\n"
        f"🖼️ AI Image Generator — upload a product photo and our AI removes "
        f"the background, optimizes it, and compresses it to push your "
        f"listing into a lower shipping slab. Save ₹25+ per order.\n\n"
        f"How it works:\n"
        f"1. Sign in and pick a tool\n"
        f"2. Upload your invoice PDFs or product photo\n"
        f"3. Let AVTools sort or optimize it\n"
        f"4. Download instantly and start saving\n\n"
        f"Get started free: https://avtools.in/label-cropper/\n\n"
        f"— AVTools Team"
    )

    try:
        send_mail(
            subject        = "🎉 Welcome to AVTools — Free Label Export + AI Image Tools Inside",
            message        = plain_message,
            from_email     = settings.DEFAULT_FROM_EMAIL,
            recipient_list = [user.email],
            html_message   = html_message,
            fail_silently  = False,
        )
        print(f"✅ Welcome email sent to {user.email}")
    except Exception as e:
        print(f"❌ Welcome email failed: {e}")