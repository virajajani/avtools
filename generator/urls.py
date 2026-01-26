from django.urls import path
from accounts.views import contact_support
from . import views

app_name = 'generator'

urlpatterns = [
    # ===============================
    # PAGES
    # ===============================


    path('', views.landing, name='landing'),      # ✅ first open landing
    path('dashboard/', views.home, name='home'),  # ✅ dashboard after login

    path('meesho-image-generator/', views.meesho_image_generator, name='meesho_image_generator'),
    
    # ===============================
    # IMAGE GENERATION
    # ===============================
    path('generate/', views.generate_images, name='generate'),
    path('download/', views.download_image, name='download'),
    
    # ===============================
    # LABEL CROPPER
    # ===============================
    path('label-cropper/', views.label_cropper, name='label_cropper'),
    path('process-labels/', views.process_labels, name='process_labels'),
  
    # ===============================
    # STATIC RIGHTS PAGES
    # ===============================
    path('terms/', views.terms, name='terms'),
    path('privacy/', views.privacy, name='privacy'),
    path("contact/", contact_support, name="contact"),

    # ===============================
    # AUTH (FRONTEND ONLY)
    # ===============================
    path('signin/', views.signin, name='signin'),
    path('signup/', views.signup, name='signup'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path("results/", views.results, name="results"),
    path("logout/", views.logout_user, name="logout"),
]