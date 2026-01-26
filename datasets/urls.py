# datasets/urls.py
"""
URL configuration for datasets app.
"""

from django.urls import path
from . import views

app_name = 'datasets'

urlpatterns = [
    # State selection API
    path('api/states/', views.get_available_states, name='api_states'),
    path('api/states/preference/', views.get_user_state_preference, name='api_state_preference'),
    path('api/states/set/', views.set_state_preference, name='api_set_state'),
    
    # SOR Rate Books API
    path('api/sor-books/', views.get_available_sor_books, name='api_sor_books'),
    
    # State selection page
    path('settings/state/', views.state_selection_page, name='state_selection'),
]
