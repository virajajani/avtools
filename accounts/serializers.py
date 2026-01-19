from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, EmailOTP, UserCredit
from .utils import (
    generate_otp,
    otp_expiry_time,
    credit_expiry_time,
    send_otp_email
)
class RegisterSerializer(serializers.ModelSerializer):
    device_id = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "password", "device_id")
        extra_kwargs = {
            "password": {"write_only": True, "min_length": 6}
        }

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered")
        return value.lower()

    def create(self, validated_data):
        device_id = validated_data.pop("device_id")
        print(f"🔑 Device ID: {device_id}")  # For logging

        user = User.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            password=validated_data["password"],
        )

        # Initial credits
        UserCredit.objects.create(
            user=user,
            balance=10,
            expires_at=credit_expiry_time()
        )

        # OTP
        otp = generate_otp()
        EmailOTP.objects.create(
            user=user,
            otp=otp,
            expires_at=otp_expiry_time()
        )

        send_otp_email(user.email, otp)
        print(f"✅ User created: {user.email}, OTP: {otp}")
        
        return user


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField()


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()
    device_id = serializers.CharField()
