# core/dashboard_views.py
"""
Dashboard views for the SaaS application.
Shows module cards, subscription status, quick actions, and announcements.
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count, Q

from accounts.models import UserProfile
from subscriptions.models import Module, UserModuleSubscription
from support.models import Announcement
from core.models import SavedWork, Organization, Membership, LetterSettings


@login_required
def dashboard(request):
    """
    Main dashboard view.
    Shows:
    - Module cards with subscription status (Active/Trial/Locked/Expired)
    - Quick stats
    - Recent activity
    - Announcements
    """
    user = request.user
    
    # Get user profile
    try:
        profile = user.account_profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user)
    
    # Get all active modules
    modules = Module.objects.filter(is_active=True).order_by('display_order')
    
    # Get user's subscriptions
    subscriptions = UserModuleSubscription.objects.filter(
        user=user,
        status__in=['active', 'trial']
    ).select_related('module', 'pricing')
    
    # Build subscription lookup
    sub_by_module = {sub.module_id: sub for sub in subscriptions}
    
    # Build module cards with status
    module_cards = []
    for module in modules:
        sub = sub_by_module.get(module.id)
        
        if sub:
            if sub.status == 'trial':
                status = 'trial'
                status_label = f'Trial ({sub.days_remaining()} days left)'
                status_class = 'warning'
            elif sub.is_active():
                status = 'active'
                status_label = 'Active'
                status_class = 'success'
            else:
                status = 'expired'
                status_label = 'Expired'
                status_class = 'danger'
            
            days_left = sub.days_remaining()
            expires_at = sub.expires_at
            usage_count = sub.usage_count
            usage_limit = sub.usage_limit
            trial_used = True  # They have/had a trial
        else:
            # Check for expired subscriptions (including trials)
            expired_sub = UserModuleSubscription.objects.filter(
                user=user,
                module=module,
                status='expired'
            ).first()
            
            # Check if trial was ever used
            trial_ever_used = UserModuleSubscription.objects.filter(
                user=user,
                module=module,
                status__in=['trial', 'expired']
            ).exists()
            
            if expired_sub:
                status = 'expired'
                status_label = 'Expired'
                status_class = 'danger'
            elif module.is_free:
                status = 'free'
                status_label = 'Free'
                status_class = 'info'
            else:
                status = 'locked'
                status_label = 'Not Subscribed'
                status_class = 'secondary'
            
            days_left = 0
            expires_at = None
            usage_count = 0
            usage_limit = module.free_tier_limit if module.is_free else 0
            trial_used = trial_ever_used
        
        module_cards.append({
            'module': module,
            'subscription': sub,
            'status': status,
            'status_label': status_label,
            'status_class': status_class,
            'days_left': days_left,
            'expires_at': expires_at,
            'usage_count': usage_count,
            'usage_limit': usage_limit,
            'trial_used': trial_used,
            'can_access': status in ('active', 'trial', 'free'),
        })
    
    # Get active announcements using the model's method (handles target audience filtering)
    announcements = Announcement.get_active(user=user)
    
    # Exclude dismissed announcements
    from support.models import UserDismissedAnnouncement
    dismissed_ids = UserDismissedAnnouncement.objects.filter(
        user=user
    ).values_list('announcement_id', flat=True)
    announcements = announcements.exclude(id__in=dismissed_ids).order_by('-starts_at')[:5]
    
    # Calculate stats
    active_subs = subscriptions.filter(status='active').count()
    trial_subs = subscriptions.filter(status='trial').count()
    total_usage = sum(s.usage_count for s in subscriptions)
    
    # Get expiring soon (within 7 days)
    expiring_soon = subscriptions.filter(
        expires_at__lte=timezone.now() + timezone.timedelta(days=7),
        expires_at__gt=timezone.now()
    )
    
    # Get user's saved works (recent in-progress works)
    saved_works = []
    try:
        membership = Membership.objects.filter(user=user).select_related('organization').first()
        if membership:
            saved_works = SavedWork.objects.filter(
                organization=membership.organization,
                user=user,
                status='in_progress'
            ).order_by('-updated_at')[:5]
    except Exception:
        pass
    
    # Check if user has filled their letter settings for better results
    letter_settings_complete = False
    try:
        letter_settings = LetterSettings.objects.filter(user=user).first()
        if letter_settings:
            # Check if at least the essential fields are filled
            letter_settings_complete = bool(
                letter_settings.officer_name or 
                letter_settings.officer_designation or 
                letter_settings.department_name
            )
    except Exception:
        pass
    
    context = {
        'user': user,
        'profile': profile,
        'module_cards': module_cards,
        'announcements': announcements,
        'saved_works': saved_works,
        'stats': {
            'active_subscriptions': active_subs,
            'trial_subscriptions': trial_subs,
            'total_usage': total_usage,
            'modules_available': modules.count(),
        },
        'expiring_soon': expiring_soon,
        'letter_settings_complete': letter_settings_complete,
    }
    
    return render(request, 'core/dashboard_new.html', context)


@login_required
def module_detail(request, module_code):
    """
    Module detail page showing pricing and subscription options.
    If user has an active subscription (including trial), redirect to the module.
    If user has never used this module, auto-start a free trial.
    """
    from django.shortcuts import get_object_or_404
    from django.contrib import messages
    from subscriptions.services.subscription_service import SubscriptionService
    
    module = get_object_or_404(Module, code=module_code, is_active=True)
    
    # Get user's subscription for this module (including expired ones)
    subscription = UserModuleSubscription.objects.filter(
        user=request.user,
        module=module
    ).order_by('-expires_at').first()
    
    # If user has active subscription or trial, redirect to the module
    if subscription and subscription.is_active():
        # Try to redirect to the module's URL
        if module.url_name:
            try:
                return redirect(module.url_name)
            except Exception:
                pass  # Fall through to show detail page
    
    # Auto-start trial if user has never used this module
    if not subscription:
        try:
            result = SubscriptionService.start_trial(request.user, module.code)
            if result['ok']:
                messages.success(request, f'Your {module.trial_days}-day free trial for {module.name} has started!')
                # Redirect to the module
                if module.url_name:
                    try:
                        return redirect(module.url_name)
                    except Exception:
                        pass
        except Exception as e:
            # Log error but continue to show pricing page
            pass
    
    # Get pricing options
    pricing_options = module.pricing_options.filter(is_active=True).order_by('duration_months')
    
    # Generate module URL for template
    module_url = None
    if module.url_name:
        try:
            from django.urls import reverse
            module_url = reverse(module.url_name)
        except Exception:
            pass
    
    context = {
        'module': module,
        'subscription': subscription,
        'pricing_options': pricing_options,
        'features': module.features or [],
        'module_url': module_url,
    }
    
    return render(request, 'core/module_detail.html', context)


@login_required
def start_trial(request, module_code):
    """Start a free trial for a module."""
    from django.shortcuts import get_object_or_404
    from django.contrib import messages
    from subscriptions.services.subscription_service import SubscriptionService
    
    if request.method != 'POST':
        return redirect('module_detail', module_code=module_code)
    
    module = get_object_or_404(Module, code=module_code, is_active=True)
    
    # Check if user already has subscription
    existing = UserModuleSubscription.objects.filter(
        user=request.user,
        module=module
    ).first()
    
    if existing:
        if existing.is_active():
            messages.warning(request, f'You already have an active subscription to {module.name}.')
        else:
            messages.error(request, f'Your free trial has expired. Please subscribe to continue using {module.name}.')
        return redirect('module_detail', module_code=module_code)
    
    # Start trial
    try:
        result = SubscriptionService.start_trial(request.user, module.code)
        if result['ok']:
            messages.success(request, f'Your {module.trial_days}-day trial for {module.name} has started!')
        else:
            messages.error(request, result.get('reason', 'Failed to start trial.'))
    except Exception as e:
        messages.error(request, f'Error starting trial: {str(e)}')
    
    return redirect('dashboard')


@login_required
def api_announcements(request):
    """
    API endpoint to fetch active announcements for AJAX polling.
    Returns announcements as JSON for dynamic updates.
    """
    from django.http import JsonResponse
    from support.models import UserDismissedAnnouncement
    from django.utils.timesince import timesince
    
    user = request.user
    
    # Get active announcements
    announcements = Announcement.get_active(user=user)
    
    # Exclude dismissed announcements
    dismissed_ids = UserDismissedAnnouncement.objects.filter(
        user=user
    ).values_list('announcement_id', flat=True)
    announcements = announcements.exclude(id__in=dismissed_ids).order_by('-starts_at')[:10]
    
    # Build response data
    data = []
    for ann in announcements:
        time_ago = timesince(ann.starts_at, timezone.now())
        # Simplify time_ago (e.g., "2 hours, 3 minutes" -> "2 hours ago")
        time_ago = time_ago.split(',')[0] + ' ago'
        
        data.append({
            'id': ann.id,
            'title': ann.title,
            'message': ann.message[:200] + '...' if len(ann.message) > 200 else ann.message,
            'type': ann.announcement_type,
            'is_dismissible': ann.is_dismissible,
            'link_url': ann.link_url,
            'link_text': ann.link_text,
            'time_ago': time_ago,
        })
    
    return JsonResponse({'announcements': data})


@login_required  
def api_dismiss_announcement(request, announcement_id):
    """
    API endpoint to dismiss an announcement.
    """
    from django.http import JsonResponse
    from support.models import UserDismissedAnnouncement
    from django.shortcuts import get_object_or_404
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    announcement = get_object_or_404(Announcement, id=announcement_id)
    
    # Record dismissal
    UserDismissedAnnouncement.objects.get_or_create(
        user=request.user,
        announcement=announcement
    )
    
    # Update dismiss count
    announcement.record_dismiss()
    
    return JsonResponse({'success': True})


@login_required
def all_announcements(request):
    """
    View to show all announcements (current and past).
    """
    from support.models import UserDismissedAnnouncement
    
    user = request.user
    
    # Get all announcements (active and recent past ones)
    all_announcements = Announcement.objects.filter(
        is_active=True
    ).order_by('-starts_at')[:50]
    
    # Get dismissed IDs
    dismissed_ids = list(UserDismissedAnnouncement.objects.filter(
        user=user
    ).values_list('announcement_id', flat=True))
    
    context = {
        'announcements': all_announcements,
        'dismissed_ids': dismissed_ids,
    }
    
    return render(request, 'core/all_announcements.html', context)
