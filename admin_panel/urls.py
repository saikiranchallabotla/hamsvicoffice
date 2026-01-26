# admin_panel/urls.py
"""
URL patterns for admin panel.
"""

from django.urls import path
from admin_panel import views
from admin_panel import analytics_views
from admin_panel import data_management_views

urlpatterns = [
    # Dashboard
    path('', views.admin_dashboard, name='admin_dashboard'),
    
    # Analytics
    path('analytics/', analytics_views.analytics_dashboard, name='admin_analytics'),
    path('analytics/user/<int:user_id>/', analytics_views.user_analytics, name='admin_user_analytics'),
    path('analytics/api/', analytics_views.analytics_api, name='admin_analytics_api'),
    path('analytics/export/<str:export_type>/', analytics_views.export_analytics, name='admin_analytics_export'),
    
    # Data Management
    path('data/', data_management_views.data_management, name='admin_data_management'),
    path('data/preview/<str:category>/', data_management_views.preview_file, name='admin_preview_file'),
    path('data/upload/<str:category>/', data_management_views.upload_file, name='admin_upload_file'),
    path('data/download/<str:category>/', data_management_views.download_file, name='admin_download_file'),
    path('data/preview-upload/', data_management_views.preview_upload, name='admin_preview_upload'),
    path('data/backup/download/<str:filename>/', data_management_views.download_backup, name='admin_download_backup'),
    path('data/backup/restore/<str:filename>/', data_management_views.restore_backup, name='admin_restore_backup'),
    path('data/backup/delete/<str:filename>/', data_management_views.delete_backup, name='admin_delete_backup'),
    
    # Module Backends (Multi-State SOR Support)
    path('data/backend/add/<str:module_code>/', data_management_views.add_module_backend, name='admin_add_module_backend'),
    path('data/backend/<int:backend_id>/edit/', data_management_views.edit_module_backend, name='admin_edit_module_backend'),
    path('data/backend/<int:backend_id>/delete/', data_management_views.delete_module_backend, name='admin_delete_module_backend'),
    path('data/backend/<int:backend_id>/preview/', data_management_views.preview_module_backend, name='admin_preview_module_backend'),
    path('data/backend/<int:backend_id>/download/', data_management_views.download_module_backend, name='admin_download_module_backend'),
    path('data/backend/<int:backend_id>/toggle-default/', data_management_views.toggle_backend_default, name='admin_toggle_backend_default'),
    
    # User Management
    path('users/', views.user_list, name='admin_user_list'),
    path('users/<int:user_id>/', views.user_detail, name='admin_user_detail'),
    path('users/<int:user_id>/edit/', views.user_edit, name='admin_user_edit'),
    path('users/<int:user_id>/toggle-status/', views.user_toggle_status, name='admin_user_toggle_status'),
    path('users/<int:user_id>/change-role/', views.user_change_role, name='admin_user_change_role'),
    
    # Module Management
    path('modules/', views.module_list, name='admin_module_list'),
    path('modules/<int:module_id>/edit/', views.module_edit, name='admin_module_edit'),
    path('modules/<int:module_id>/pricing/', views.pricing_edit, name='admin_pricing_edit'),
    
    # Subscription Management
    path('subscriptions/', views.subscription_list, name='admin_subscription_list'),
    path('subscriptions/grant/<int:user_id>/', views.grant_subscription, name='admin_grant_subscription'),
    path('subscriptions/<uuid:subscription_id>/revoke/', views.revoke_subscription, name='admin_revoke_subscription'),
    
    # Support Tickets
    path('tickets/', views.ticket_list, name='admin_ticket_list'),
    path('tickets/<uuid:ticket_id>/', views.ticket_detail, name='admin_ticket_detail'),
    
    # Announcements
    path('announcements/', views.announcement_list, name='admin_announcement_list'),
    path('announcements/<int:announcement_id>/edit/', views.announcement_edit, name='admin_announcement_edit'),
    path('announcements/<int:announcement_id>/delete/', views.announcement_delete, name='admin_announcement_delete'),
    
    # FAQ Management
    path('faq/', views.faq_list, name='admin_faq_list'),
    path('faq/category/<int:category_id>/edit/', views.faq_category_edit, name='admin_faq_category_edit'),
    path('faq/item/<int:item_id>/edit/', views.faq_item_edit, name='admin_faq_item_edit'),
    path('faq/item/<int:item_id>/delete/', views.faq_item_delete, name='admin_faq_item_delete'),
    
    # Payments
    path('payments/', views.payment_list, name='admin_payment_list'),
    path('payments/<uuid:payment_id>/', views.payment_detail, name='admin_payment_detail'),
]
