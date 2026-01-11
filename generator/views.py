from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from .utils import generate_image_variations, calculate_pricing, CATEGORIES
import base64

from .label_utils import crop_meesho_labels_to_pdf


# ===============================
# HOME / DASHBOARD
# ===============================

def home(request):
    return render(request, 'home.html')


#==============================
# Landing Page
#==============================

def landing(request):
    return render(request, 'landing.html')

# ===============================
# MEESHO IMAGE GENERATOR PAGE
# ===============================

def meesho_image_generator(request):
    context = {
        'categories': CATEGORIES
    }
    return render(request, 'meesho_image_generator.html', context)


# ===============================
# AUTH PAGES (FRONTEND ONLY)
# ===============================

def signin(request):
    return render(request, 'user/signin.html')


def signup(request):
    return render(request, 'user/signup.html')

def forgot_password(request):
    return render(request, 'user/forgot_password.html')

# ===============================
# IMAGE GENERATION
# ===============================

def generate_images(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=400)

    image = request.FILES.get('product_image')
    category = request.POST.get('category')
    net_weight = float(request.POST.get('net_weight', 0))
    meesho_price = float(request.POST.get('meesho_price', 0))
    return_price = float(request.POST.get('return_price', 0))
    mrp = float(request.POST.get('mrp', 0))
    num_images = int(request.POST.get('num_images', 55))

    if not image or not category:
        return JsonResponse({'error': 'Missing data'}, status=400)

    variations = generate_image_variations(image, category, num_images)

    for variation in variations:
        variation['pricing'] = calculate_pricing(
            cost_price=meesho_price,
            selling_price=meesho_price,
            shipping_rate=variation['shipping_rate']
        )
        variation['extra'] = {
            'net_weight': net_weight,
            'return_price': return_price,
            'mrp': mrp,
        }

    context = {
        'variations': variations,
        'category': CATEGORIES.get(category, {}).get('name', category),
        'total_images': len(variations)
    }

    return render(request, 'generator/results.html', context)



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
        
        # Generate clean filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_filename = f"meesho_labels_{timestamp}.pdf"
        
        # Return PDF as automatic download with proper headers
        response = HttpResponse(output_pdf_bytes, content_type='application/pdf')
        # Use both filename and filename* for better browser compatibility
        response['Content-Disposition'] = f'attachment; filename="{output_filename}"; filename*=UTF-8\'\'{output_filename}'
        response['Content-Length'] = str(len(output_pdf_bytes))
        response['Content-Type'] = 'application/pdf'
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        
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