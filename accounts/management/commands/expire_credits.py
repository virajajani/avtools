# accounts/management/commands/expire_credits.py
#
# Also create these two empty files if they don't exist:
#   accounts/management/__init__.py
#   accounts/management/commands/__init__.py
#
# Run:  python manage.py expire_credits
# Cron: 0 0 * * * /path/to/venv/bin/python manage.py expire_credits

from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import UserCredit, CreditHistory


class Command(BaseCommand):
    help = "Zero out expired credits for all users and log to CreditHistory."

    def handle(self, *args, **options):
        expired_qs = UserCredit.objects.filter(
            expires_at__lt=timezone.now(),
            balance__gt=0,
        ).select_related("user")

        count = 0

        for credit in expired_qs:
            old_balance    = credit.balance
            credit.balance = 0
            credit.save()

            CreditHistory.objects.create(
                user=credit.user,
                credits=old_balance,
                transaction_type="EXPIRE",
                previous_balance=old_balance,
                current_balance=0,
                description=(
                    f"Credits expired on "
                    f"{credit.expires_at.strftime('%d-%m-%Y %I:%M %p')}"
                ),
            )

            self.stdout.write(
                f"  ⏰ Expired {old_balance} credits → {credit.user.email}"
            )
            count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Done. {count} account(s) had credits expired."
            )
        )