from django import template
from django.utils import timezone
from django.db.models import Sum

register = template.Library()

@register.inclusion_tag('partials/account_modal.html', takes_context=True)
def account_modal(context):
    request = context['request']
    user = request.user
    
    if not user.is_authenticated:
        return context
    
    from payments.models import PaymentTransaction
    from accounts.models import UserCredit
    
    transactions = PaymentTransaction.objects.filter(
        user=user
    ).select_related("plan").order_by("-created_at")[:20]
    
    all_tx = PaymentTransaction.objects.filter(user=user)
    total_spent = all_tx.filter(status="SUCCESS").aggregate(t=Sum("amount"))["t"] or 0
    total_purchases = all_tx.filter(status="SUCCESS").count()
    
    user_credit = UserCredit.objects.filter(user=user).first()
    now = timezone.now()
    is_expired = False
    days_left = None

    if user_credit and user_credit.expires_at:
        is_expired = user_credit.expires_at < now
        if not is_expired:
            days_left = (user_credit.expires_at - now).days

    return {
        **context,
        'transactions': transactions,
        'user_credit': user_credit,
        'total_spent': total_spent,
        'total_purchases': total_purchases,
        'is_expired': is_expired,
        'days_left': days_left,
    }