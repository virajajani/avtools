from django.utils import timezone
from django.db.models import Sum

def account_modal_data(request):
    if not request.user.is_authenticated:
        return {}

    from payments.models import PaymentTransaction
    from accounts.models import UserCredit

    transactions = PaymentTransaction.objects.filter(
        user=request.user
    ).exclude(status="PENDING").select_related("plan").order_by("-created_at")[:10]

    all_tx = PaymentTransaction.objects.filter(user=request.user)
    total_spent     = all_tx.filter(status="SUCCESS").aggregate(t=Sum("amount"))["t"] or 0
    total_purchases = all_tx.filter(status="SUCCESS").count()

    user_credit = UserCredit.objects.filter(user=request.user).first()
    now         = timezone.now()
    is_expired  = False
    days_left   = None

    if user_credit and user_credit.expires_at:
        is_expired = user_credit.expires_at < now
        if not is_expired:
            days_left = (user_credit.expires_at - now).days

    return {
        "transactions":     transactions,
        "user_credit":      user_credit,
        "total_spent":      total_spent,
        "total_purchases":  total_purchases,
        "is_expired":       is_expired,
        "days_left":        days_left,
    }