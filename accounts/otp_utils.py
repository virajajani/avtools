# accounts/otp_utils.py
#
# Email-OTP helpers for registration.
#   - cryptographically secure codes (secrets, not random)
#   - codes stored hashed, expire in 10 min, max 5 wrong attempts
#   - resend cooldown (60s) + hourly send cap, to stop email-bombing
#   - disposable / temporary email blocking

import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import EmailOTP, User

OTP_LENGTH             = 6
OTP_EXPIRY_MINUTES     = 10
OTP_MAX_ATTEMPTS       = 5
OTP_RESEND_COOLDOWN    = 60      # seconds
OTP_MAX_SENDS_PER_HOUR = 5


# ═══════════════════════════════════════════════
# DISPOSABLE / FAKE EMAIL BLOCKING
# ═══════════════════════════════════════════════
# Seeded with the throw-away domains seen in your user list, plus the
# most common ones. For full coverage run:  pip install disposable-email-domains
# (it is picked up automatically below). You can also add your own domains in
# settings.py:  EXTRA_BLOCKED_EMAIL_DOMAINS = {"baddomain.com"}

_BUILTIN_DISPOSABLE = {
    # seen in your signups
    "otp1second.com", "otp2s.com", "otp3s.com", "hlongmail.com", "herclan.com",
    # common temp-mail providers
    "mailinator.com", "guerrillamail.com", "guerrillamail.net", "sharklasers.com",
    "10minutemail.com", "10minutemail.net", "tempmail.com", "temp-mail.org",
    "tempmailo.com", "tempmail.net", "yopmail.com", "yopmail.net", "trashmail.com",
    "getnada.com", "nada.email", "throwawaymail.com", "dispostable.com",
    "maildrop.cc", "fakeinbox.com", "mohmal.com", "emailondeck.com",
    "mintemail.com", "mailnesia.com", "burnermail.io", "moakt.com",
    "mytemp.email", "tmpmail.org", "tmpmail.net", "mail.tm", "1secmail.com",
    "1secmail.net", "1secmail.org", "discard.email", "spamgourmet.com",
}

try:
    from disposable_email_domains import blocklist as _PKG_BLOCKLIST
except ImportError:                      # package optional
    _PKG_BLOCKLIST = set()


def _blocked_domains():
    extra = set(getattr(settings, "EXTRA_BLOCKED_EMAIL_DOMAINS", set()))
    return _BUILTIN_DISPOSABLE | set(_PKG_BLOCKLIST) | extra


def is_disposable_email(email: str) -> bool:
    domain = email.rsplit("@", 1)[-1].strip().lower()
    blocked = _blocked_domains()
    # match the domain itself and any parent (x.mailinator.com -> mailinator.com)
    parts = domain.split(".")
    return any(".".join(parts[i:]) in blocked for i in range(len(parts) - 1))


# ═══════════════════════════════════════════════
# TRUSTED-PROVIDER ALLOWLIST  (checked BEFORE any OTP is sent)
# ═══════════════════════════════════════════════
# Only addresses from well-known mailbox providers can register. This kills
# typo/fake domains (gmial.com), throw-away domains and made-up domains in one
# rule. The OTP then proves the mailbox itself really exists.
#
# A seller using a custom business email? Add the domain in settings.py:
#     EXTRA_ALLOWED_EMAIL_DOMAINS = {"mycompany.com"}

ALLOWED_EMAIL_DOMAINS = {
    # Google
    "gmail.com", "googlemail.com",
    # Yahoo
    "yahoo.com", "yahoo.in", "yahoo.co.in", "ymail.com", "rocketmail.com",
    # Microsoft
    "outlook.com", "outlook.in", "hotmail.com", "hotmail.co.uk",
    "live.com", "live.in", "msn.com",
    # Apple
    "icloud.com", "me.com", "mac.com",
    # Others (global + India)
    "aol.com", "proton.me", "protonmail.com", "pm.me",
    "zoho.com", "zohomail.com", "zohomail.in",
    "rediffmail.com", "rediff.com", "mail.com", "gmx.com", "fastmail.com",
}

_EMAIL_RE = re.compile(r"^[a-z0-9][a-z0-9._%-]*@[a-z0-9.-]+\.[a-z]{2,}$")


def _allowed_domains():
    extra = set(getattr(settings, "EXTRA_ALLOWED_EMAIL_DOMAINS", set()))
    return ALLOWED_EMAIL_DOMAINS | {d.lower() for d in extra}


def validate_signup_email(email: str):
    """Returns an error string, or None if the email is acceptable."""
    email = (email or "").strip().lower()

    if "@" not in email:
        return "Please enter a valid email address."

    local, domain = email.rsplit("@", 1)

    if "+" in local:
        return "Email aliases using '+' are not allowed. Please use your main email address."

    if not _EMAIL_RE.match(email):
        return "Please enter a valid email address."

    if domain not in _allowed_domains():
        return ("Please enter a valid email address.")

    # second layer — only matters for domains you added via EXTRA_ALLOWED_EMAIL_DOMAINS
    if is_disposable_email(email):
        return ("Temporary / disposable email addresses are not allowed. "
                "Please use your real email address.")
    return None


def gmail_alias_exists(email: str) -> bool:
    """
    Gmail ignores dots: a.b@gmail.com == ab@gmail.com == a.b@googlemail.com.
    Stops one person farming free credits with dotted variants of one inbox.
    """
    local, domain = email.strip().lower().rsplit("@", 1)
    if domain not in {"gmail.com", "googlemail.com"}:
        return False

    base = local.replace(".", "")
    if not base:
        return False

    pattern = r"^" + r"\.*".join(re.escape(c) for c in base) + r"@(gmail|googlemail)\.com$"
    return (
        User.objects
        .filter(email__iregex=pattern, is_email_verified=True)
        .exclude(email__iexact=email)
        .exists()
    )


# ═══════════════════════════════════════════════
# OTP ISSUE / VERIFY
# ═══════════════════════════════════════════════

class OTPThrottled(Exception):
    def __init__(self, retry_after: int, message: str):
        super().__init__(message)
        self.retry_after = retry_after
        self.message     = message


def issue_otp(user):
    """Create + email a fresh OTP. Raises OTPThrottled if requested too fast."""
    now = timezone.now()
    qs  = EmailOTP.objects.filter(user=user)

    last = qs.order_by("-created_at").first()
    if last:
        wait = OTP_RESEND_COOLDOWN - (now - last.created_at).total_seconds()
        if wait > 0:
            secs = int(wait) + 1
            raise OTPThrottled(secs, f"Please wait {secs}s before requesting another code.")

    sent_last_hour = qs.filter(created_at__gte=now - timedelta(hours=1)).count()
    if sent_last_hour >= OTP_MAX_SENDS_PER_HOUR:
        raise OTPThrottled(3600, "Too many code requests. Please try again in an hour.")

    otp = "".join(secrets.choice("0123456789") for _ in range(OTP_LENGTH))

    record = EmailOTP.objects.create(
        user       = user,
        otp        = make_password(otp),
        expires_at = now + timedelta(minutes=OTP_EXPIRY_MINUTES),
    )

    try:
        send_verification_email(user, otp)
    except Exception:
        record.delete()
        raise

    # only invalidate older codes once the new one was actually delivered
    qs.exclude(pk=record.pk).filter(is_used=False).update(is_used=True)
    return record


def verify_otp(user, otp):
    """Returns (ok: bool, message: str)."""
    otp = (otp or "").strip()

    with transaction.atomic():
        record = (
            EmailOTP.objects.select_for_update()
            .filter(user=user, is_used=False)
            .order_by("-created_at")
            .first()
        )

        if not record:
            return False, "No active code. Please request a new one."

        if record.is_expired():
            record.is_used = True
            record.save(update_fields=["is_used"])
            return False, "This code has expired. Please request a new one."

        if record.attempts >= OTP_MAX_ATTEMPTS:
            record.is_used = True
            record.save(update_fields=["is_used"])
            return False, "Too many incorrect attempts. Please request a new code."

        record.attempts += 1

        valid = (
            otp.isdigit()
            and len(otp) == OTP_LENGTH
            and check_password(otp, record.otp)
        )

        if not valid:
            left = OTP_MAX_ATTEMPTS - record.attempts
            if left <= 0:
                record.is_used = True
            record.save(update_fields=["attempts", "is_used"])
            if left <= 0:
                return False, "Too many incorrect attempts. Please request a new code."
            return False, f"Incorrect code. {left} attempt{'s' if left != 1 else ''} left."

        record.is_used = True
        record.save(update_fields=["attempts", "is_used"])
        return True, "ok"


# ═══════════════════════════════════════════════
# EMAIL
# ═══════════════════════════════════════════════

def send_verification_email(user, otp: str):
    first_name = user.first_name or user.email.split("@")[0]

    digits_html = "".join(
        f'<span style="display:inline-block;width:44px;height:52px;background:#ffffff;'
        f'border:2px solid #e0e7ff;border-radius:10px;font-size:26px;font-weight:900;'
        f'color:#2563eb;line-height:52px;text-align:center;margin:0 3px;'
        f'box-shadow:0 2px 8px rgba(99,102,241,0.12);">{d}</span>'
        for d in otp
    )

    html_message = f"""
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Verify your email</title></head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:'Inter',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f1f5f9;padding:40px 20px;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" border="0"
             style="max-width:560px;width:100%;background:#ffffff;border-radius:24px;overflow:hidden;
                    box-shadow:0 20px 60px rgba(15,23,42,0.10);">

        <tr>
          <td style="background:linear-gradient(135deg,#3b82f6 0%,#8b5cf6 100%);padding:36px 40px;text-align:center;">
            <div style="font-size:28px;font-weight:900;color:#ffffff;letter-spacing:-0.5px;margin-bottom:6px;">⚡ AVTools</div>
            <div style="font-size:13px;color:rgba(255,255,255,0.80);font-weight:500;">Verify your email address</div>
          </td>
        </tr>

        <tr>
          <td style="padding:40px 40px 32px;">
            <h1 style="margin:0 0 8px;font-size:22px;font-weight:800;color:#0f172a;text-align:center;">
              Confirm your email
            </h1>
            <p style="margin:0 0 28px;font-size:15px;color:#64748b;text-align:center;line-height:1.6;">
              Hi <strong style="color:#0f172a;">{first_name}</strong>, enter this code on the AVTools
              sign-up page to finish creating your account.
            </p>

            <div style="background:linear-gradient(135deg,#f8fafc,#f1f5f9);border:2px dashed #c7d2fe;
                        border-radius:16px;padding:28px 24px;text-align:center;margin-bottom:28px;">
              <p style="margin:0 0 10px;font-size:12px;font-weight:700;color:#6366f1;
                        text-transform:uppercase;letter-spacing:0.1em;">Your Verification Code</p>
              <div style="display:inline-block;">{digits_html}</div>
              <p style="margin:14px 0 0;font-size:12px;color:#94a3b8;font-weight:500;">
                ⏰ This code expires in <strong style="color:#ef4444;">{OTP_EXPIRY_MINUTES} minutes</strong>
              </p>
            </div>

            <div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:12px;padding:14px 18px;">
              <p style="margin:0;font-size:13px;color:#92400e;line-height:1.6;">
                🔒 <strong>Security notice:</strong> If you didn't try to create an AVTools account,
                you can safely ignore this email. Never share this code with anyone.
              </p>
            </div>
          </td>
        </tr>

        <tr><td style="padding:0 40px;"><div style="height:1px;background:#e2e8f0;"></div></td></tr>

        <tr>
          <td style="padding:24px 40px 32px;text-align:center;">
            <p style="margin:0 0 8px;font-size:12px;color:#94a3b8;line-height:1.6;">
              Sent to <strong style="color:#64748b;">{user.email}</strong>
            </p>
            <p style="margin:0;font-size:11px;color:#cbd5e1;">© 2026 AVTools. All rights reserved.</p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
    """

    plain_message = (
        f"Hi {first_name},\n\n"
        f"Your AVTools email verification code is: {otp}\n\n"
        f"It expires in {OTP_EXPIRY_MINUTES} minutes. "
        f"Never share this code with anyone.\n\n"
        f"If you didn't try to create an account, please ignore this email.\n\n"
        f"— AVTools Team"
    )

    send_mail(
        subject        = "🔐 Your AVTools verification code",
        message        = plain_message,
        from_email     = settings.DEFAULT_FROM_EMAIL,
        recipient_list = [user.email],
        html_message   = html_message,
        fail_silently  = False,
    )