from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework.authtoken.models import Token

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import User, UserDevice
from .serializers import RegisterSerializer, LoginSerializer
from .utils import token_expiry_time
import random
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.conf import settings

from django.shortcuts import render, redirect
from .models import ContactSupport

@method_decorator(csrf_exempt, name='dispatch')
class RegisterAPI(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        print(f"📥 Received data: {request.data}")  # Debug

        serializer = RegisterSerializer(data=request.data)

        if not serializer.is_valid():
            print(f"❌ Validation errors: {serializer.errors}")
            return Response(
                {"error": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ✅ Create user
        user = serializer.save()

        # ✅ No OTP: Directly verify user
        user.is_email_verified = True
        user.save()

        # ✅ Create token
        token, _ = Token.objects.get_or_create(user=user)

        # ✅ Save device info
        device_id = request.data.get("device_id")
        if device_id:
            UserDevice.objects.update_or_create(
                user=user,
                device_id=device_id,
                defaults={
                    "token_expiry": token_expiry_time(),
                    "last_login": timezone.now()
                }
            )

        return Response({
            "message": "Account created successfully!",
            "token": token.key,
            "expires_at": token_expiry_time(),
            "user": {
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name
            }
        }, status=status.HTTP_201_CREATED)


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

        # ✅ No OTP check anymore (optional)
        # if not user.is_email_verified:
        #     return Response({"error": "Email not verified"}, status=403)

        token, _ = Token.objects.get_or_create(user=user)

        UserDevice.objects.update_or_create(
            user=user,
            device_id=serializer.validated_data["device_id"],
            defaults={
                "token_expiry": token_expiry_time(),
                "last_login": timezone.now()
            }
        )

        user.last_login = timezone.now()
        user.save()

        return Response({
            "token": token.key,
            "expires_at": token_expiry_time(),
            "user": {
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name
            }
        })

@method_decorator(csrf_exempt, name="dispatch")
class ForgotPasswordAPI(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        email = request.data.get("email", "").strip().lower()

        if not email:
            return Response({"message": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response({"message": "Email not found"}, status=status.HTTP_404_NOT_FOUND)

        otp = str(random.randint(100000, 999999))

        # ✅ Save in session
        request.session["reset_email"] = user.email
        request.session["reset_otp"] = otp

        # ✅ Send OTP to email
        send_mail(
            subject="AVTools Password Reset OTP",
            message=f"Your OTP is: {otp}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False
        )

        print("✅ OTP sent to email:", user.email)

        return Response({"message": "OTP sent successfully"}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class VerifyOTPAPI(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        otp = request.data.get("otp", "").strip()

        if request.session.get("reset_email") != email:
            return Response({"message": "Invalid email"}, status=status.HTTP_400_BAD_REQUEST)

        if request.session.get("reset_otp") != otp:
            return Response({"message": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message": "OTP verified"}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class ResetPasswordAPI(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        password = request.data.get("password", "").strip()

        if not password:
            return Response({"message": "Password is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response({"message": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        user.password = make_password(password)
        user.save()

        # clear session otp
        request.session.pop("reset_email", None)
        request.session.pop("reset_otp", None)

        return Response({"message": "Password reset successful"}, status=status.HTTP_200_OK)


def contact_support(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        mobile = request.POST.get("mobile")
        email = request.POST.get("email")
        message = request.POST.get("message")

        # Save to DB
        ContactSupport.objects.create(
            first_name=first_name,
            last_name=last_name,
            mobile_number=mobile,
            email=email,
            message=message
        )

        # Send Email
        # email_subject = "New Contact Support Message - AVTools"
        # email_body = f"""
        #     New support message received:

        #     Name: {first_name} {last_name}
        #     Mobile: {mobile}
        #     Email: {email}

        #     Message:
        #     {message}
        #     """

        # send_mail(
        #     email_subject,
        #     email_body,
        #     settings.DEFAULT_FROM_EMAIL,
        #     ["avtools.in@gmail.com"],  # YOUR SUPPORT EMAIL
        #     fail_silently=False,
        # )

        return render(request, "user/contact_success.html")

    return render(request, "user/contact.html")