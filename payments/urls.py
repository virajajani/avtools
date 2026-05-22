from django.urls import path
from payments import views
from .views import (
    get_credit_plans, 
    create_order, 
    verify_payment, 
    refund_captured_payment_rest, 
    payment_page, 
    PaymentHistory
)
from .admin_refund_views import refund_admin_view, process_refund_ajax

urlpatterns = [
    path("credit-plans/", get_credit_plans, name="credit-plans"),
    path("create-order/", create_order, name="create-order"),
    path("verify-payment/", verify_payment, name="verify-payment"),
    path("refund-payment/", refund_captured_payment_rest, name="refund-payment"),
    path("payment-page/", views.payment_page, name="payment-page"),
    path("payment-history/", PaymentHistory.as_view(), name="payment-history"),
    path("admin/refund/", refund_admin_view, name="refund-admin"),
    path("admin/refund/process/", process_refund_ajax, name="process-refund"),
    path("payment-callback/", views.payment_callback, name="payment-callback"),
]