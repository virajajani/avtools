from rest_framework import serializers
from .models import User, UserCredit
from .utils import credit_expiry_time


class RegisterSerializer(serializers.ModelSerializer):
    device_id = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "password", "device_id")
        extra_kwargs = {"password": {"write_only": True, "min_length": 6}}

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered")
        return value.lower()

    def validate_password(self, value):
        if len(value) < 6:
            raise serializers.ValidationError("Password must be at least 6 characters")
        return value

    def create(self, validated_data):
        validated_data.pop("device_id")  # ✅ removed from serializer

        user = User.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            password=validated_data["password"],
        )

        # ✅ No OTP verification
        user.is_email_verified = True
        user.save()

        # ✅ Free credits
        UserCredit.objects.create(
            user=user,
            balance=10,
            expires_at=credit_expiry_time()
        )

        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()
    device_id = serializers.CharField()
