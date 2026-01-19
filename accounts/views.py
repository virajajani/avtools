from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework.authtoken.models import Token

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import User, EmailOTP, UserDevice
from .serializers import (
    RegisterSerializer,
    VerifyOTPSerializer,
    LoginSerializer
)
from .utils import token_expiry_time

@method_decorator(csrf_exempt, name='dispatch')
class RegisterAPI(APIView):
    authentication_classes = []
    permission_classes = []
    
    def post(self, request):
        print(f"📥 Received data: {request.data}")  # Debug
        
        serializer = RegisterSerializer(data=request.data)
        
        if not serializer.is_valid():
            print(f"❌ Validation errors: {serializer.errors}")  # Debug
            return Response(
                {"error": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer.save()
        return Response(
            {"message": "OTP sent to email"},
            status=status.HTTP_201_CREATED
        )


@method_decorator(csrf_exempt, name="dispatch")
class VerifyOTPAPI(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.filter(email=serializer.validated_data["email"]).first()
        if not user:
            return Response({"error": "User not found"}, status=404)

        otp_obj = EmailOTP.objects.filter(user=user).last()
        if not otp_obj or otp_obj.is_expired():
            return Response({"error": "OTP expired"}, status=400)

        if otp_obj.otp != serializer.validated_data["otp"]:
            return Response({"error": "Invalid OTP"}, status=400)

        user.is_email_verified = True
        user.save()
        otp_obj.delete()

        return Response({"message": "Email verified successfully"})


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

        if not user.is_email_verified:
            return Response({"error": "Email not verified"}, status=403)

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
