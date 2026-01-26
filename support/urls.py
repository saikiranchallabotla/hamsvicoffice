# support/urls.py
"""
URL patterns for support app.
"""

from django.urls import path
from support import views

urlpatterns = [
    # Help center (public)
    path('', views.help_center_view, name='help_center'),
    path('search/', views.search_help_view, name='search_help'),
    path('faq/<slug:category_slug>/', views.faq_category_view, name='faq_category'),
    path('guide/<slug:guide_slug>/', views.guide_view, name='guide'),
    
    # Tickets (authenticated)
    path('tickets/', views.my_tickets_view, name='my_tickets'),
    path('tickets/new/', views.create_ticket_view, name='create_ticket'),
    path('tickets/<uuid:ticket_id>/', views.view_ticket_view, name='view_ticket'),
    path('tickets/<uuid:ticket_id>/close/', views.close_ticket_view, name='close_ticket'),
]
