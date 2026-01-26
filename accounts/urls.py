# accounts/urls.py
"""
URL patterns for accounts app.
"""

from django.urls import path
from accounts import views

urlpatterns = [
    # Template-based auth
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('resend-otp/', views.resend_otp_view, name='resend_otp'),
    path('logout/', views.logout_view, name='logout'),
    
    # Session management
    path('sessions/', views.active_sessions_view, name='active_sessions'),
    path('sessions/<int:session_id>/revoke/', views.revoke_session_view, name='revoke_session'),
    path('logout-all/', views.logout_all_view, name='logout_all'),
    
    # Settings & Profile management
    path('settings/', views.settings_view, name='settings'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
    path('profile/change-phone/', views.change_phone_view, name='change_phone'),
    path('profile/change-phone/verify/', views.verify_phone_change_view, name='verify_phone_change'),
    path('profile/change-email/', views.change_email_view, name='change_email'),
    path('profile/change-email/verify/', views.verify_email_change_view, name='verify_email_change'),
    path('profile/notifications/', views.notification_prefs_view, name='notification_prefs'),
    path('profile/export/', views.export_data_view, name='export_data'),
    path('profile/delete/', views.delete_account_view, name='delete_account'),
    
    # Backend preferences (Multi-State SOR Support)
    path('preferences/backends/', views.backend_preferences_view, name='backend_preferences'),
    path('preferences/backends/set/', views.set_backend_preference_view, name='set_backend_preference'),
    path('preferences/backends/clear/', views.clear_backend_preference_view, name='clear_backend_preference'),
    
    # API endpoints
    path('api/auth/request-otp/', views.api_request_otp, name='api_request_otp'),
    path('api/auth/verify-otp/', views.api_verify_otp, name='api_verify_otp'),
    path('api/auth/logout/', views.api_logout, name='api_logout'),
]
