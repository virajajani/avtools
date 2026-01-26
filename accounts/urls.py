from django.urls import path
from .views import RegisterAPI, LoginAPI
from .views import ForgotPasswordAPI, VerifyOTPAPI, ResetPasswordAPI

urlpatterns = [
    path("register/", RegisterAPI.as_view(), name="register"),
    path("login/", LoginAPI.as_view(), name="login"),
    path("forgot-password/", ForgotPasswordAPI.as_view(), name="forgot_password"),
    path("verify-otp/", VerifyOTPAPI.as_view(), name="verify_otp"),
    path("reset-password/", ResetPasswordAPI.as_view(), name="reset_password"),
]
