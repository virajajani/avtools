import random
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail

def generate_otp():
    return str(random.randint(100000, 999999))

def otp_expiry_time():
    return timezone.now() + timedelta(minutes=10)

def token_expiry_time():
    return timezone.now() + timedelta(days=7)

def credit_expiry_time():
    return timezone.now() + timedelta(days=30)

def send_otp_email(email, otp):
    send_mail(
        subject="AVTools Email Verification OTP",
        message=f"Your OTP is {otp}. Valid for 10 minutes.",
        from_email=None,
        recipient_list=[email],
        fail_silently=False,
    )
