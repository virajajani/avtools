# generator/views.py
# Credits now read/written exclusively from accounts.UserCredit
# CreditHistory is recorded for every deduction

from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from .utils import generate_image_variations, calculate_pricing, CATEGORIES
import base64
import traceback
from datetime import datetime

from .label_utils import crop_meesho_labels_to_pdf
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from .models import UserProfile, GenerationHistory, ActiveSession, MonthlyLabelSummary
from django.contrib.auth import get_user_model
User = get_user_model()
from django.views.decorators.http import require_POST
from django.contrib.auth import update_session_auth_hash
from django.http import JsonResponse, HttpResponse
from django.utils.timezone import now
from products.models import SubSubCategory

# ── NEW: single source of truth for credits ───────────────────────────────
from accounts.models import UserCredit, CreditHistory

from accounts.utils import expire_user_credits   # add to imports at top

# ==============================
# Landing Page
# ==============================

def landing(request):
    return render(request, 'landing.html')


# ===============================
# HELPERS
# ===============================

def get_user_credit(user):
    """
    Return (UserCredit, balance).
    Creates the row with 0 balance if it doesn't exist yet.
    """
    credit, _ = UserCredit.objects.get_or_create(user=user)
    return credit


# ===============================
# HOME / DASHBOARD (AFTER LOGIN)
# ===============================

@login_required(login_url='generator:signin')
def home(request):
    credit = get_user_credit(request.user)
    username = request.user.username or "U"
    initials = username[0].upper()
    device_ctx = load_active_devices(request)

    return render(request, "home.html", {
        "credits": credit.balance,
        "initials": initials,
        **device_ctx,
    })


# ===============================
# MEESHO IMAGE GENERATOR PAGE
# ===============================

@login_required(login_url='generator:signin')
def meesho_image_generator(request):
    credit = get_user_credit(request.user)
    username = request.user.username or "U"
    initials = username[0].upper()
    device_ctx = load_active_devices(request)

    recent_generations = GenerationHistory.objects.filter(
        user=request.user
    ).prefetch_related("categories").order_by('-created_at')[:6]

    return render(request, "meesho_image_generator.html", {
        "categories": CATEGORIES,
        "credits": credit.balance,
        "initials": initials,
        "recent_generations": recent_generations,
        **device_ctx,
    })


# ===============================
# AUTH PAGES
# ===============================

def signin(request):
    if request.method == "POST":
        email    = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()

        if not email or not password:
            messages.error(request, "Email and password are required.")
            return redirect("generator:signin")

        user = authenticate(request, email=email, password=password)
        if user is None:
            user = authenticate(request, username=email, password=password)

        if user is None:
            messages.error(request, "Invalid email or password!")
            return redirect("generator:signin")

        login(request, user)

        # Ensure UserCredit row exists
        get_user_credit(user)

        if request.session.session_key:
            ActiveSession.objects.update_or_create(
                session_key=request.session.session_key,
                defaults={
                    "user": user,
                    "ip_address": request.META.get("REMOTE_ADDR"),
                    "user_agent": request.META.get("HTTP_USER_AGENT", "")
                }
            )

        return redirect("generator:home")

    return render(request, "user/signin.html")


def signup(request):
    if request.method == "POST":
        name     = request.POST.get("name")
        email    = request.POST.get("email")
        password = request.POST.get("password")

        if User.objects.filter(username=email).exists():
            messages.error(request, "Account already exists with this email!")
            return redirect("generator:signup")

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=name
        )

        # Give 10 free credits via UserCredit (single source of truth)
        from django.utils import timezone
        from datetime import timedelta
        credit = UserCredit.objects.create(
            user=user,
            balance=10,
            expires_at=timezone.now() + timedelta(days=365),
        )
        CreditHistory.objects.create(
            user=user,
            credits=10,
            transaction_type="ADD",
            previous_balance=0,
            current_balance=10,
            description="Welcome bonus — 10 free credits",
        )

        messages.success(request, "Account created successfully! You got 10 free credits.")
        return redirect("generator:signin")

    return render(request, "user/signup.html")


def forgot_password(request):
    return render(request, 'user/forgot_password.html')


def logout_user(request):
    if request.session.session_key:
        ActiveSession.objects.filter(
            session_key=request.session.session_key
        ).delete()
    logout(request)
    return redirect("generator:signin")


# ===============================
# IMAGE GENERATION
# ===============================

@login_required(login_url='generator:signin')
def generate_images(request):

    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=400)

    # ── Credit check via UserCredit ───────────────────────────────────────────
    credit = get_user_credit(request.user)

    if credit.balance < 1:
        messages.error(request, "You have 0 credits left. Please recharge.")
        return redirect("generator:meesho_image_generator")

    # ── Form data ─────────────────────────────────────────────────────────────
    image        = request.FILES.get("product_image")
    meesho_price = request.POST.get("meesho_price", "").strip()
    selected_raw = request.POST.get("selected_categories", "").strip()

    # ── Validation ────────────────────────────────────────────────────────────
    if not image:
        messages.error(request, "Please upload a product image.")
        return redirect("generator:meesho_image_generator")

    if not meesho_price:
        messages.error(request, "Please enter the Meesho price.")
        return redirect("generator:meesho_image_generator")

    if not selected_raw:
        messages.error(request, "Please select at least one category.")
        return redirect("generator:meesho_image_generator")

    # ── Parse category IDs ────────────────────────────────────────────────────
    raw_ids = [x.strip() for x in selected_raw.split(",") if x.strip()]
    category_ids = []
    for x in raw_ids:
        try:
            category_ids.append(int(x))
        except ValueError:
            pass

    if not category_ids:
        messages.error(request, "Invalid categories selected. Please try again.")
        return redirect("generator:meesho_image_generator")

    categories = SubSubCategory.objects.filter(id__in=category_ids)

    found_ids = set(categories.values_list("id", flat=True))
    missing   = [i for i in category_ids if i not in found_ids]
    if missing:
        print(f"[generate_images] WARNING: category IDs not found in DB: {missing}")

    if not categories.exists():
        messages.error(request, "No valid categories found. Please reselect.")
        return redirect("generator:meesho_image_generator")

    # ── Save generation history ────────────────────────────────────────────────
    try:
        history = GenerationHistory.objects.create(
            user=request.user,
            meesho_price=meesho_price,
            uploaded_image=image,
        )
        history.categories.set(categories)
        history.save()
    except Exception as e:
        print(f"[generate_images] DB error: {e}")
        messages.error(request, "Could not save generation. Please try again.")
        return redirect("generator:meesho_image_generator")

    # ── Deduct 1 credit + record history ──────────────────────────────────────
    previous_balance = credit.balance
    credit.balance  -= 1
    credit.save()

    CreditHistory.objects.create(
        user=request.user,
        credits=1,
        transaction_type="DEDUCT",
        previous_balance=previous_balance,
        current_balance=credit.balance,
        description=f"Image generation — history #{history.id}",
    )

    # ── Store session reference ────────────────────────────────────────────────
    request.session["last_history_id"] = history.id
    request.session.modified = True

    return redirect("generator:results")


# ===============================
# RESULTS
# ===============================

@login_required(login_url='generator:signin')
def results(request):
    history_id = request.session.get("last_history_id")

    if not history_id:
        messages.error(request, "No generated results found.")
        return redirect("generator:meesho_image_generator")

    try:
        history = (
            GenerationHistory.objects
            .prefetch_related("categories")
            .get(id=history_id, user=request.user)
        )
    except GenerationHistory.DoesNotExist:
        messages.error(request, "Generation not found.")
        return redirect("generator:meesho_image_generator")

    category_names = [cat.name for cat in history.categories.all()]

    variations = generate_image_variations(
        history.uploaded_image,
        ", ".join(category_names),
        55
    )

    for variation in variations:
        variation["pricing"] = calculate_pricing(
            cost_price=float(history.meesho_price),
            selling_price=float(history.meesho_price),
            shipping_rate=variation["shipping_rate"]
        )

    credit = get_user_credit(request.user)

    return render(request, "generator/results.html", {
        "variations":   variations,
        "categories":   history.categories.all(),
        "total_images": len(variations),
        "credits_left": credit.balance,
        "history":      history,
    })


# ===============================
# DOWNLOAD IMAGE
# ===============================

@login_required(login_url='generator:signin')
def download_image(request):
    image_data = request.POST.get('image_data')

    if not image_data:
        return HttpResponse('No image data', status=400)

    image_bytes = base64.b64decode(image_data)
    response = HttpResponse(image_bytes, content_type='image/jpeg')
    response['Content-Disposition'] = 'attachment; filename="meesho_image.jpg"'
    return response


# ===============================
# LABEL CROPPER PAGE
# ===============================

def label_cropper(request):
    return render(request, 'crop/label_cropper.html')


# ===============================
# PROCESS LABELS
# ===============================

def process_labels(request):

    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=400)

    pdf_file = request.FILES.get('label_pdf')

    if not pdf_file:
        return JsonResponse({'error': 'No PDF file uploaded'}, status=400)

    if not pdf_file.name.lower().endswith('.pdf'):
        return JsonResponse({'error': 'Please upload a PDF file'}, status=400)

    if pdf_file.size > 50 * 1024 * 1024:
        return JsonResponse({'error': 'File too large. Max size is 50MB'}, status=400)

    try:
        print("\n" + "=" * 70)
        print("📄 STARTING PDF PROCESS")
        print("=" * 70)
        print(f"Processing PDF: {pdf_file.name}")
        print(f"PDF Size: {pdf_file.size} bytes")

        result           = crop_meesho_labels_to_pdf(pdf_file)
        output_pdf_bytes = result["pdf_bytes"]
        product_summary  = result["product_summary"]
        total_labels     = result["total_labels"]

        if not output_pdf_bytes:
            return JsonResponse({'error': 'Failed to generate PDF'}, status=400)

        print(f"\n✅ Generated PDF Size: {len(output_pdf_bytes)} bytes")
        print("\n📦 PRODUCT SUMMARY")
        for courier, products in product_summary.items():
            print(f"\n🚚 {courier}")
            for product, qty in products.items():
                print(f"   {product} = {qty} Labels")
        print(f"\n✅ TOTAL LABELS: {total_labels}")

        current_time  = now()
        current_date  = current_time.date()
        current_month = current_date.replace(day=1)

        from .models import DailyLabelSummary

        daily_summary, _ = DailyLabelSummary.objects.get_or_create(date=current_date)
        daily_summary.total_pdfs   += 1
        daily_summary.total_labels += total_labels
        daily_summary.save()

        print(f"\n📅 DAILY SUMMARY UPDATED")
        print(f"Date: {daily_summary.date}")
        print(f"Daily PDFs: {daily_summary.total_pdfs}")
        print(f"Daily Labels: {daily_summary.total_labels}")

        monthly_summary, _ = MonthlyLabelSummary.objects.get_or_create(month=current_month)
        monthly_summary.total_pdfs   += 1
        monthly_summary.total_labels += total_labels
        monthly_summary.save()

        print(f"\n📊 MONTHLY SUMMARY UPDATED")
        print(f"Month: {monthly_summary.month}")
        print(f"Monthly PDFs: {monthly_summary.total_pdfs}")
        print(f"Monthly Labels: {monthly_summary.total_labels}")

        timestamp       = datetime.now().strftime('%H%M%S')
        output_filename = f"avtools_crop_label_{timestamp}.pdf"
        pdf_base64      = base64.b64encode(output_pdf_bytes).decode('utf-8')

        print(f"\n📥 Sending PDF: {output_filename}")
        print("=" * 70)

        return JsonResponse({
            'success':         True,
            'filename':        output_filename,
            'pdf_base64':      pdf_base64,
            'total_labels':    total_labels,
            'product_summary': product_summary,
            'daily_summary': {
                'date':         str(daily_summary.date),
                'total_pdfs':   daily_summary.total_pdfs,
                'total_labels': daily_summary.total_labels,
                'last_used':    daily_summary.last_used.strftime('%d-%m-%Y %I:%M %p'),
            },
            'monthly_summary': {
                'month':        str(monthly_summary.month),
                'total_pdfs':   monthly_summary.total_pdfs,
                'total_labels': monthly_summary.total_labels,
                'last_used':    monthly_summary.last_used.strftime('%d-%m-%Y %I:%M %p'),
            },
        })

    except ValueError as e:
        print(f"\n❌ ValueError: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)

    except Exception as e:
        print(f"\n❌ Error processing PDF: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'error': f'Error processing PDF: {str(e)}'}, status=500)


# ===============================
# PROFILE / SECURITY ACTIONS
# ===============================

@login_required(login_url='generator:signin')
@require_POST
def update_profile(request):
    user       = request.user
    first_name = request.POST.get("first_name")
    last_name  = request.POST.get("last_name")
    avatar     = request.FILES.get("avatar")

    if first_name:
        user.first_name = first_name
    if last_name:
        user.last_name = last_name
    user.save()

    profile, _ = UserProfile.objects.get_or_create(user=user)
    if avatar:
        profile.avatar = avatar
        profile.save()

    messages.success(request, "Profile updated successfully.")
    return redirect("generator:home")


@login_required(login_url='generator:signin')
@require_POST
def set_password(request):
    password1 = request.POST.get("password1")
    password2 = request.POST.get("password2")

    if not password1 or not password2:
        messages.error(request, "Password fields cannot be empty.")
        return redirect("generator:home")

    if password1 != password2:
        messages.error(request, "Passwords do not match.")
        return redirect("generator:home")

    user = request.user
    user.set_password(password1)
    user.save()
    update_session_auth_hash(request, user)
    messages.success(request, "Password updated successfully.")
    return redirect("generator:home")


@login_required(login_url='generator:signin')
@require_POST
def delete_account(request):
    user = request.user
    logout(request)
    user.delete()
    messages.success(request, "Your account has been permanently deleted.")
    return redirect("generator:signin")


@login_required(login_url='generator:signin')
@require_POST
def disconnect_google(request):
    try:
        request.user.socialaccount_set.all().delete()
        messages.success(request, "Google account disconnected.")
    except Exception:
        messages.error(request, "No connected Google account found.")
    return redirect("generator:home")


# ===============================
# ACTIVE DEVICES
# ===============================

def load_active_devices(request):
    session_key = request.session.session_key

    if request.user.is_authenticated and session_key:
        ActiveSession.objects.update_or_create(
            session_key=session_key,
            defaults={
                "user":       request.user,
                "ip_address": request.META.get("REMOTE_ADDR"),
                "user_agent": request.META.get("HTTP_USER_AGENT", "")
            }
        )
        return {
            "sessions":        ActiveSession.objects.filter(user=request.user),
            "current_session": session_key,
        }

    return {"sessions": [], "current_session": None}


# ===============================
# STATIC RIGHTS PAGES
# ===============================

def terms(request):
    return render(request, 'rights/terms.html', {'user': request.user})

def privacy(request):
    return render(request, 'rights/privacy.html', {'user': request.user})

def refund_policy(request):
    return render(request, 'rights/refund-policy.html', {'user': request.user})

def contact(request):
    return render(request, 'rights/contact.html', {'user': request.user})

def about_us(request):
    return render(request, 'rights/about-us.html', {'user': request.user})

 
def get_user_credit(user):
    """
    Returns the UserCredit for this user.
    Automatically zeros the balance and logs history if credits have expired.
    """
    return expire_user_credits(user)
 