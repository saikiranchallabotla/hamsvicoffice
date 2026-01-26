# subscriptions/urls.py
"""
URL patterns for subscriptions app.
"""

from django.urls import path
from subscriptions import views

urlpatterns = [
    # Pricing page (public)
    path('pricing/', views.pricing_view, name='pricing'),
    
    # Module access (subscription required page)
    path('access/<str:module_code>/', views.module_access_view, name='module_access'),
    path('access/<str:module_code>/trial/', views.start_trial_view, name='subscriptions_start_trial'),
    
    # User subscription management
    path('my-subscriptions/', views.my_subscriptions_view, name='my_subscriptions'),
    
    # Payment history
    path('payment-history/', views.payment_history_view, name='payment_history'),
    
    # Checkout
    path('checkout/<str:module_code>/<int:pricing_id>/', views.checkout_view, name='checkout'),
    
    # Payment API
    path('api/create-order/', views.create_order_view, name='create_order'),
    path('api/verify-payment/', views.verify_payment_view, name='verify_payment'),
    
    # Subscription actions
    path('cancel/<uuid:subscription_id>/', views.cancel_subscription_view, name='cancel_subscription'),
]
