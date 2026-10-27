from django.urls import path
from .views import  RegisterAPI, LoginAPI, ForgotPasswordAPI, VerifyOTPAPI, ResetPasswordAPI , VerifyRegistrationOTPAPI, ResendRegistrationOTPAPI 
from accounts import views

urlpatterns = [
    # ── Auth APIs ──────────────────────────────────────────
    path("register/",        RegisterAPI.as_view(),        name="register"),
    path("login/",           LoginAPI.as_view(),           name="login"),
    path("forgot-password/", ForgotPasswordAPI.as_view(),  name="forgot_password"),
    path("verify-otp/",      VerifyOTPAPI.as_view(),       name="verify_otp"),
    path("reset-password/",  ResetPasswordAPI.as_view(),   name="reset_password"),

    path("register/verify-otp/", VerifyRegistrationOTPAPI.as_view()),
    path("register/resend-otp/", ResendRegistrationOTPAPI.as_view()),

    # ── Device check ───────────────────────────────────────
    path("device/check/",  views.check_device,  name="check_device"),

    # ── Review APIs ────────────────────────────────────────
    path("review/submit/", views.submit_review,  name="submit_review"),
    path("review/list/",   views.get_reviews,    name="get_reviews"),

    path("api/auth/google/", views.GoogleAuthAPI.as_view(), name="google_auth"),
]