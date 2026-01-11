from django.urls import path
from . import views

app_name = 'generator'

urlpatterns = [
    # Pages
    path('', views.home, name='home'),
    path('landing/', views.landing, name='landing'),
    path('meesho-image-generator/', views.meesho_image_generator, name='meesho_image_generator'),

    # Image generation actions
    path('generate/', views.generate_images, name='generate'),
    path('download/', views.download_image, name='download'),

    # Auth (frontend only)
    path('signin/', views.signin, name='signin'),
    path('signup/', views.signup, name='signup'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),

]
