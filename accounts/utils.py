import random
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail

from django.utils import timezone
from accounts.models import UserCredit, CreditHistory


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


def expire_user_credits(user):
    """
    Check if the user's credits have expired.
    If yes → zero the balance and write an EXPIRE CreditHistory row.
    Always returns the up-to-date UserCredit instance.
    """
    credit, _ = UserCredit.objects.get_or_create(user=user)

    if credit.balance > 0 and credit.is_expired():
        old_balance    = credit.balance
        credit.balance = 0
        credit.save()

        CreditHistory.objects.create(
            user=user,
            credits=old_balance,
            transaction_type="EXPIRE",
            previous_balance=old_balance,
            current_balance=0,
            description=(
                f"Credits expired on "
                f"{credit.expires_at.strftime('%d-%m-%Y %I:%M %p')}"
            ),
        )

    return credit