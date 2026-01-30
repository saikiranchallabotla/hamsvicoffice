# core/security_utils.py
"""
Security utilities for the application.
Provides safe error handling, input validation, and security helpers.
"""

import logging
import re
from typing import Optional, Any
from django.conf import settings

logger = logging.getLogger(__name__)


def safe_error_message(exception: Exception, default_message: str = "An error occurred. Please try again.") -> str:
    """
    Return a safe error message for user display.
    
    In DEBUG mode, returns the full exception message.
    In production, returns a generic message and logs the real error.
    
    Args:
        exception: The exception that occurred
        default_message: User-friendly message to show in production
        
    Returns:
        Safe error message string
    """
    if settings.DEBUG:
        return str(exception)
    
    # Log the real error for debugging
    logger.error(f"Error (sanitized for user): {exception}", exc_info=True)
    
    return default_message


def safe_int(value: Any, default: int = 0) -> int:
    """
    Safely convert a value to integer.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Integer value or default
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert a value to float.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Float value or default
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a filename to prevent path traversal and other attacks.
    
    Args:
        filename: Original filename
        max_length: Maximum allowed length
        
    Returns:
        Sanitized filename
    """
    # Remove path separators
    filename = filename.replace('/', '').replace('\\', '')
    
    # Remove null bytes and other control characters
    filename = re.sub(r'[\x00-\x1f\x7f]', '', filename)
    
    # Remove leading dots to prevent hidden files
    filename = filename.lstrip('.')
    
    # Limit length
    if len(filename) > max_length:
        # Preserve extension
        parts = filename.rsplit('.', 1)
        if len(parts) == 2:
            name, ext = parts
            max_name_length = max_length - len(ext) - 1
            filename = f"{name[:max_name_length]}.{ext}"
        else:
            filename = filename[:max_length]
    
    return filename or 'unnamed_file'


def validate_file_extension(filename: str, allowed_extensions: list) -> bool:
    """
    Validate that a file has an allowed extension.
    
    Args:
        filename: The filename to check
        allowed_extensions: List of allowed extensions (with dots, e.g., ['.xlsx', '.xls'])
        
    Returns:
        True if extension is allowed, False otherwise
    """
    if not filename:
        return False
    
    # Normalize extensions to lowercase with dots
    allowed = [ext.lower() if ext.startswith('.') else f'.{ext.lower()}' for ext in allowed_extensions]
    
    # Get file extension
    if '.' not in filename:
        return False
    
    ext = '.' + filename.rsplit('.', 1)[1].lower()
    return ext in allowed


def mask_sensitive_data(data: str, visible_chars: int = 4, mask_char: str = '*') -> str:
    """
    Mask sensitive data like phone numbers or emails for display.
    
    Args:
        data: The sensitive data to mask
        visible_chars: Number of characters to keep visible at the end
        mask_char: Character to use for masking
        
    Returns:
        Masked string
    """
    if not data:
        return ''
    
    data = str(data)
    
    if len(data) <= visible_chars:
        return mask_char * len(data)
    
    masked_length = len(data) - visible_chars
    return mask_char * masked_length + data[-visible_chars:]


def log_security_event(event_type: str, user=None, ip_address: str = None, details: dict = None):
    """
    Log a security-relevant event.
    
    Args:
        event_type: Type of security event (e.g., 'login_failed', 'permission_denied')
        user: User object if available
        ip_address: Client IP address
        details: Additional details dictionary
    """
    log_data = {
        'event': event_type,
        'user': str(user) if user else 'anonymous',
        'ip': ip_address or 'unknown',
        'details': details or {}
    }
    
    logger.warning(f"SECURITY_EVENT: {log_data}")
    
    # Optionally store in database audit log
    try:
        from datasets.models import AuditLog
        AuditLog.objects.create(
            user=user if user and hasattr(user, 'id') else None,
            action=event_type,
            details=str(details) if details else '',
            ip_address=ip_address or '',
        )
    except Exception:
        # Don't fail if audit logging fails
        pass
