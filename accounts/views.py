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
