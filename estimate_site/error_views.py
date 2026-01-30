# estimate_site/error_views.py
"""
Custom error handlers with user-friendly error pages.
These handlers are used in production when DEBUG=False.
"""

import logging
from django.shortcuts import render
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def _is_ajax(request):
    """Check if request is an AJAX request."""
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
        request.content_type == 'application/json' or
        'application/json' in request.headers.get('Accept', '')
    )


def bad_request(request, exception=None):
    """
    Handle 400 Bad Request errors.
    Usually caused by malformed requests or invalid data.
    """
    if _is_ajax(request):
        return JsonResponse({
            'ok': False,
            'error': 'Bad request. Please check your input and try again.',
            'code': 400
        }, status=400)
    
    return render(request, '404.html', status=400)  # Reuse 404 template for 400


def permission_denied(request, exception=None):
    """
    Handle 403 Forbidden errors.
    Shown when user doesn't have permission to access a resource.
    """
    logger.warning(
        f"403 Forbidden: {request.path} - User: {request.user} - IP: {request.META.get('REMOTE_ADDR')}"
    )
    
    if _is_ajax(request):
        return JsonResponse({
            'ok': False,
            'error': 'You do not have permission to access this resource.',
            'code': 403
        }, status=403)
    
    return render(request, '403.html', status=403)


def page_not_found(request, exception=None):
    """
    Handle 404 Not Found errors.
    Shown when a page or resource doesn't exist.
    """
    if _is_ajax(request):
        return JsonResponse({
            'ok': False,
            'error': 'The requested resource was not found.',
            'code': 404
        }, status=404)
    
    return render(request, '404.html', status=404)


def server_error(request):
    """
    Handle 500 Internal Server errors.
    Shown when an unexpected error occurs.
    
    Note: This handler doesn't receive exception parameter
    because it's called for uncaught exceptions.
    """
    logger.error(
        f"500 Server Error: {request.path} - User: {request.user} - IP: {request.META.get('REMOTE_ADDR')}"
    )
    
    if _is_ajax(request):
        return JsonResponse({
            'ok': False,
            'error': 'An unexpected error occurred. Please try again later.',
            'code': 500
        }, status=500)
    
    return render(request, '500.html', status=500)
