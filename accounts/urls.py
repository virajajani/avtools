from django.urls import path
from .views import RegisterAPI, VerifyOTPAPI, LoginAPI

urlpatterns = [
    path("register/", RegisterAPI.as_view(), name="register"),
    path("verify-otp/", VerifyOTPAPI.as_view(), name="verify-otp"),
    path("login/", LoginAPI.as_view(), name="login"),
]
