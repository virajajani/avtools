from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from .utils import generate_image_variations, calculate_pricing, CATEGORIES
import base64

from .label_utils import crop_meesho_labels_to_pdf
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.shortcuts import redirect
from django.contrib.auth import logout
from .models import UserProfile, GenerationHistory,ActiveSession
from django.contrib.auth import get_user_model
User = get_user_model()
from django.views.decorators.http import require_POST
from django.contrib.auth import update_session_auth_hash



#==============================
# Landing Page
#==============================

def landing(request):
    return render(request, 'landing.html')

# ===============================
# HOME / DASHBOARD (AFTER LOGIN)
# ===============================

@login_required(login_url='generator:signin')
def home(request):
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={"credits": 10}
    )

    username = request.user.username or "U"
    initials = username[0].upper()

    device_ctx = load_active_devices(request)

    return render(request, "home.html", {
        "credits": profile.credits,
        "initials": initials,
        **device_ctx,
    })
 

# ===============================
# MEESHO IMAGE GENERATOR PAGE
# ===============================
@login_required(login_url='generator:signin')
def meesho_image_generator(request):
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={"credits": 10}
    )

    username = request.user.username or "U"
    initials = username[0].upper()

    device_ctx = load_active_devices(request)

    # ✅ FETCH RECENT GENERATIONS
    recent_generations = GenerationHistory.objects.filter(
        user=request.user
    ).order_by('-created_at')[:6]

    return render(request, "meesho_image_generator.html", {
        "categories": CATEGORIES,
        "credits": profile.credits,
        "initials": initials,
        "recent_generations": recent_generations,   # ✅ ADD THIS
        **device_ctx,
    })


# ===============================
# AUTH PAGES (FRONTEND ONLY)
# ===============================




def signin(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()

        if not email or not password:
            messages.error(request, "Email and password are required.")
            return redirect("generator:signin")

        # ✅ Try email-based login
        user = authenticate(request, email=email, password=password)

        # ✅ Fallback to username-based login
        if user is None:
            user = authenticate(request, username=email, password=password)

        if user is None:
            messages.error(request, "Invalid email or password!")
            return redirect("generator:signin")

        # ✅ Login user
        login(request, user)

        # ✅ Ensure profile exists
        profile, created = UserProfile.objects.get_or_create(user=user)
        if created:
            profile.credits = 10
            profile.save()

        # ✅ Track active device (REAL)
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
        name = request.POST.get("name")
        email = request.POST.get("email")
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

        UserProfile.objects.create(user=user, credits=10)

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

    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={"credits": 10}
    )

    # Safety fix
    if profile.credits is None:
        profile.credits = 10
        profile.save()

    # ✅ credit check
    if profile.credits < 1:
        messages.error(request, "You have 0 credits left. Please recharge.")
        return redirect("generator:meesho_image_generator")

    image = request.FILES.get("product_image")
    category = request.POST.get("category")
    net_weight = float(request.POST.get("net_weight", 0))
    meesho_price = float(request.POST.get("meesho_price", 0))
    return_price = float(request.POST.get("return_price", 0))
    mrp = float(request.POST.get("mrp", 0))
    num_images = int(request.POST.get("num_images", 55))

    if not image or not category:
        messages.error(request, "Please upload image and select category!")
        return redirect("generator:meesho_image_generator")

    # ✅ Save generation details in DB (history)
    history = GenerationHistory.objects.create(
        user=request.user,
        category=category,
        net_weight=net_weight,
        meesho_price=meesho_price,
        return_price=return_price,
        mrp=mrp,
        uploaded_image=image
    )

    # ✅ Cut 1 credit ONLY ONCE
    profile.credits -= 1
    profile.save()

    # ✅ Redirect to results page (GET) => Refresh safe ✅
    request.session["last_history_id"] = history.id
    return redirect("generator:results")



@login_required(login_url='generator:signin')
def results(request):
    history_id = request.session.get("last_history_id")

    if not history_id:
        messages.error(request, "No generated results found. Please generate images first.")
        return redirect("generator:meesho_image_generator")

    history = GenerationHistory.objects.get(id=history_id, user=request.user)

    variations = generate_image_variations(history.uploaded_image, history.category, 55)

    for variation in variations:
        variation["pricing"] = calculate_pricing(
            cost_price=history.meesho_price,
            selling_price=history.meesho_price,
            shipping_rate=variation["shipping_rate"]
        )
        variation["extra"] = {
            "net_weight": history.net_weight,
            "return_price": history.return_price,
            "mrp": history.mrp,
        }

    profile = UserProfile.objects.get(user=request.user)

    return render(request, "generator/results.html", {
        "variations": variations,
        "category": CATEGORIES.get(history.category, {}).get("name", history.category),
        "total_images": len(variations),
        "credits_left": profile.credits
    })

# ===============================
# DOWNLOAD IMAGE
# ===============================

def download_image(request):
    image_data = request.POST.get('image_data')
    if not image_data:
        return HttpResponse('No image data', status=400)

    image_bytes = base64.b64decode(image_data)
    response = HttpResponse(image_bytes, content_type='image/jpeg')
    response['Content-Disposition'] = 'attachment; filename="meesho_image.jpg"'
    return response

# Add this to your views.py

# Add this to your views.py

# Add this to your views.py

from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from .label_utils import crop_meesho_labels_to_pdf
import traceback
from datetime import datetime


def label_cropper(request):
    """Display the label cropper interface"""
    return render(request, 'crop/label_cropper.html')


def process_labels(request):
    """Process uploaded PDF and automatically download cropped labels as PDF"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=400)
    
    pdf_file = request.FILES.get('label_pdf')
    
    if not pdf_file:
        return JsonResponse({'error': 'No PDF file uploaded'}, status=400)
    
    # Validate file type
    if not pdf_file.name.lower().endswith('.pdf'):
        return JsonResponse({'error': 'Please upload a PDF file'}, status=400)
    
    # Validate file size (max 50MB)
    if pdf_file.size > 50 * 1024 * 1024:
        return JsonResponse({'error': 'File too large. Max size is 50MB'}, status=400)
    
    try:
        print(f"Processing PDF: {pdf_file.name}, Size: {pdf_file.size} bytes")
        
        # Process the PDF - FIXED: removed use_simple_detection parameter
        output_pdf_bytes = crop_meesho_labels_to_pdf(pdf_file)
        
        if not output_pdf_bytes:
            return JsonResponse({'error': 'Failed to generate PDF'}, status=400)
        
        print(f"Generated PDF size: {len(output_pdf_bytes)} bytes")
        
        # Generate clean filename with time only
        from datetime import datetime
        timestamp = datetime.now().strftime('%H%M%S')
        output_filename = f"avtools_crop_label_{timestamp}.pdf"
        
        # Return PDF as automatic download with simple headers
        response = HttpResponse(output_pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename={output_filename}'
        response['Content-Length'] = str(len(output_pdf_bytes))
        
        print(f"Sending PDF: {output_filename}")
        return response
    
    except ValueError as e:
        # Specific errors (like no labels found)
        print(f"ValueError: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)
    
    except Exception as e:
        # Log the full error for debugging
        print(f"Error processing PDF: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'error': f'Error processing PDF: {str(e)}'}, status=500)
    
# ===============================
# PROFILE / SECURITY ACTIONS
# ===============================

@login_required(login_url='generator:signin')
@require_POST
def update_profile(request):
    user = request.user

    first_name = request.POST.get("first_name")
    last_name = request.POST.get("last_name")
    avatar = request.FILES.get("avatar")

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
                "user": request.user,
                "ip_address": request.META.get("REMOTE_ADDR"),
                "user_agent": request.META.get("HTTP_USER_AGENT", "")
            }
        )

        return {
            "sessions": ActiveSession.objects.filter(user=request.user),
            "current_session": session_key,
        }

    return {
        "sessions": [],
        "current_session": None,
    }


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