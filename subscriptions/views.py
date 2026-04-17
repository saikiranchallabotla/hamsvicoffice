# subscriptions/views.py
"""
Subscription views for pricing, checkout, and subscription management.
"""

from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone

from subscriptions.models import Module, ModulePricing, UserModuleSubscription, Payment


@login_required
def module_access_view(request, module_code):
    """
    Module access page - shows trial/subscription options.
    Users can view this page even if they have trial access (to upgrade).
    Admins/superusers can view the page to see pricing options.
    """
    from subscriptions.models import ModuleBundle
    
    module = get_object_or_404(Module, code=module_code, is_active=True)
    
    # Check if user has active subscription (paid or trial)
    existing_sub = UserModuleSubscription.objects.filter(
        user=request.user,
        module=module,
        status__in=['active', 'trial'],
        expires_at__gt=timezone.now()
    ).first()
    
    # If user has active subscription, redirect to module
    if existing_sub and not (request.user.is_staff or request.user.is_superuser):
        if module.url_name:
            try:
                return redirect(module.url_name)
            except Exception:
                pass
        redirect_url = request.session.pop('subscription_redirect', None)
        if redirect_url:
            return redirect(redirect_url)
        return redirect('dashboard')
    
    # Check current subscription status (for display)
    current_sub = existing_sub  # Already fetched above
    
    # Check if trial available
    # A user has "used" their trial if they have any subscription record
    # for this module that was a trial (pricing is NULL for trials).
    # This covers status='trial' (active/expired) AND revoked trials (status='cancelled' with no pricing).
    existing_trial = UserModuleSubscription.objects.filter(
        user=request.user,
        module=module,
        pricing__isnull=True,  # trial subscriptions have no pricing
    ).first()

    # Also check for a currently active trial specifically
    has_used_trial = existing_trial is not None

    trial_available = False
    trial_remaining_delta = None
    if not existing_trial:
        # Never used trial
        trial_available = True
        trial_remaining_delta = module.trial_duration_timedelta
    elif existing_trial.expires_at and existing_trial.expires_at < timezone.now():
        # Trial expired — check if admin extended the trial duration since then
        time_used = existing_trial.expires_at - existing_trial.started_at
        new_duration = module.trial_duration_timedelta
        if new_duration > time_used:
            trial_available = True
            trial_remaining_delta = new_duration - time_used
    
    # Get pricing options
    plans = ModulePricing.objects.filter(
        module=module,
        is_active=True
    ).order_by('duration_months')
    
    # Reason for access denial
    reason = request.GET.get('reason', 'You need an active subscription to access this module.')
    
    # Build human-readable trial duration
    if trial_remaining_delta and trial_remaining_delta != module.trial_duration_timedelta:
        # Re-offered trial: show remaining time
        total_secs = int(trial_remaining_delta.total_seconds())
        rem_days = total_secs // 86400
        rem_hours = (total_secs % 86400) // 3600
        trial_parts = []
        if rem_days:
            trial_parts.append(f'{rem_days} day{"s" if rem_days != 1 else ""}')
        if rem_hours:
            trial_parts.append(f'{rem_hours} hour{"s" if rem_hours != 1 else ""}')
        trial_duration_str = ' and '.join(trial_parts) or 'a few minutes'
    else:
        trial_parts = []
        if module.trial_days:
            trial_parts.append(f'{module.trial_days} day{"s" if module.trial_days != 1 else ""}')
        if module.trial_hours:
            trial_parts.append(f'{module.trial_hours} hour{"s" if module.trial_hours != 1 else ""}')
        trial_duration_str = ' and '.join(trial_parts) or '1 day'
    
    context = {
        'module': module,
        'trial_available': trial_available,
        'trial_days': module.trial_days,
        'trial_hours': module.trial_hours,
        'trial_duration_str': trial_duration_str,
        'plans': plans if module.payments_enabled else [],
        'payments_enabled': module.payments_enabled,
        'reason': reason,
        'current_subscription': current_sub,
    }

    # Add active bundle info if this module is part of a bundle
    try:
        bundle = ModuleBundle.objects.filter(
            is_active=True, modules=module
        ).prefetch_related('modules', 'bundle_pricing').first()
        if bundle:
            bundle_plans = bundle.get_active_pricing()
            if bundle_plans.exists():
                context['bundle'] = bundle
                context['bundle_plans'] = bundle_plans
    except Exception:
        pass
    
    return render(request, 'subscriptions/module_access.html', context)


@login_required
@require_POST
def start_trial_view(request, module_code):
    """
    Start a free trial for a module.
    """
    module = get_object_or_404(Module, code=module_code, is_active=True)

    # Check for any existing subscription (active, trial, expired, cancelled)
    existing_sub = UserModuleSubscription.objects.filter(
        user=request.user,
        module=module,
    ).first()

    if existing_sub:
        # Already has an active paid subscription
        if existing_sub.status == 'active' and existing_sub.expires_at > timezone.now():
            messages.info(request, f'You already have an active subscription for {module.name}.')
            redirect_url = request.session.pop('subscription_redirect', None)
            if redirect_url:
                return redirect(redirect_url)
            return redirect('dashboard')

        # Active trial
        if existing_sub.status == 'trial' and existing_sub.expires_at > timezone.now():
            messages.info(request, f'You already have an active trial for {module.name}.')
            redirect_url = request.session.pop('subscription_redirect', None)
            if redirect_url:
                return redirect(redirect_url)
            return redirect('dashboard')

        # Expired trial — check if admin extended trial duration
        if existing_sub.status == 'trial' and existing_sub.expires_at and existing_sub.expires_at < timezone.now():
            time_used = existing_sub.expires_at - existing_sub.started_at
            new_duration = module.trial_duration_timedelta
            if new_duration > time_used:
                remaining = new_duration - time_used
                existing_sub.expires_at = timezone.now() + remaining
                existing_sub.save(update_fields=['expires_at'])
                total_secs = int(remaining.total_seconds())
                rem_days = total_secs // 86400
                rem_hours = (total_secs % 86400) // 3600
                parts = []
                if rem_days:
                    parts.append(f'{rem_days} day{"s" if rem_days != 1 else ""}')
                if rem_hours:
                    parts.append(f'{rem_hours} hour{"s" if rem_hours != 1 else ""}')
                duration_str = ' and '.join(parts) or 'a few minutes'
                messages.success(request, f'Your free trial for {module.name} has been extended by {duration_str}!')
                redirect_url = request.session.pop('subscription_redirect', None)
                if redirect_url:
                    return redirect(redirect_url)
                return redirect('dashboard')
            messages.error(request, f'You have already used your free trial for {module.name}.')
            return redirect('module_access', module_code=module_code)

        # Expired/cancelled paid subscription (has pricing) — allow a fresh trial
        # But NOT if this was a revoked trial (no pricing = was a trial)
        if existing_sub.status in ('expired', 'cancelled', 'suspended'):
            if existing_sub.pricing is None:
                # This was a trial that got revoked — don't allow another trial
                messages.error(request, f'You have already used your free trial for {module.name}.')
                return redirect('module_access', module_code=module_code)
            trial_expires = timezone.now() + module.trial_duration_timedelta
            existing_sub.status = 'trial'
            existing_sub.started_at = timezone.now()
            existing_sub.expires_at = trial_expires
            existing_sub.usage_count = 0
            existing_sub.usage_limit = module.max_usage_per_subscription if module.max_usage_per_subscription >= 0 else 0
            existing_sub.cancelled_at = None
            existing_sub.save()
    else:
        # No existing subscription — create a new trial
        trial_expires = timezone.now() + module.trial_duration_timedelta
        UserModuleSubscription.objects.create(
            user=request.user,
            module=module,
            status='trial',
            started_at=timezone.now(),
            expires_at=trial_expires,
            usage_limit=module.max_usage_per_subscription if module.max_usage_per_subscription >= 0 else 0,
        )
    
    # Build human-readable duration string
    parts = []
    if module.trial_days:
        parts.append(f'{module.trial_days} day{"s" if module.trial_days != 1 else ""}')
    if module.trial_hours:
        parts.append(f'{module.trial_hours} hour{"s" if module.trial_hours != 1 else ""}')
    duration_str = ' and '.join(parts) or '1 day'
    
    messages.success(request, f'🎉 Your {duration_str} free trial for {module.name} is now active!')
    
    # Redirect to originally intended URL
    redirect_url = request.session.pop('subscription_redirect', None)
    if redirect_url:
        return redirect(redirect_url)
    
    return redirect('dashboard')


def pricing_view(request):
    """
    Redirect to dashboard - pricing is now shown per module on module_access pages.
    """
    return redirect('dashboard')


@login_required
def my_subscriptions_view(request):
    """
    User's subscription management page.
    Shows active, trial, and expired subscriptions.
    """
    subscriptions = UserModuleSubscription.objects.filter(
        user=request.user
    ).select_related('module', 'pricing').order_by('-created_at')
    
    # Group by status
    active_subs = [s for s in subscriptions if s.status == 'active' and s.is_active()]
    trial_subs = [s for s in subscriptions if s.status == 'trial' and s.is_active()]
    expired_subs = [s for s in subscriptions if s.status in ('expired', 'cancelled') or not s.is_active()]
    
    context = {
        'active_subscriptions': active_subs,
        'trial_subscriptions': trial_subs,
        'expired_subscriptions': expired_subs,
    }
    
    return render(request, 'subscriptions/my_subscriptions.html', context)


@login_required
def checkout_view(request, module_code, pricing_id):
    """
    Checkout page for purchasing a subscription.
    """
    module = get_object_or_404(Module, code=module_code, is_active=True)
    pricing = get_object_or_404(ModulePricing, id=pricing_id, module=module, is_active=True)
    
    # Check if user already has active subscription
    existing = UserModuleSubscription.objects.filter(
        user=request.user,
        module=module,
        status__in=['active', 'trial']
    ).first()
    
    context = {
        'module': module,
        'pricing': pricing,
        'existing_subscription': existing,
    }
    
    return render(request, 'subscriptions/checkout.html', context)


@login_required
@require_POST
def create_order_view(request):
    """
    Create a Razorpay order for payment.
    """
    from subscriptions.services.payment_service import PaymentService
    
    pricing_id = request.POST.get('pricing_id')
    coupon_code = request.POST.get('coupon_code', '').strip() or None
    
    try:
        pricing = ModulePricing.objects.get(id=pricing_id, is_active=True)
    except ModulePricing.DoesNotExist:
        return JsonResponse({'ok': False, 'reason': 'Invalid pricing option.'}, status=400)
    
    # Create order using the service
    result = PaymentService.create_order(
        user=request.user,
        module_codes=[pricing.module.code],
        duration_months=pricing.duration_months,
        coupon_code=coupon_code
    )
    
    if result['ok']:
        data = result.get('data', {})
        return JsonResponse({
            'ok': True,
            'order_id': data.get('razorpay_order_id'),
            'internal_order_id': data.get('order_id'),
            'amount': data.get('amount'),
            'currency': data.get('currency', 'INR'),
            'key': data.get('razorpay_key_id'),
            'prefill': {
                'name': data.get('user_name', ''),
                'email': data.get('user_email', ''),
            }
        })
    
    return JsonResponse({'ok': False, 'reason': result.get('reason', 'Failed to create order.')}, status=400)


@login_required
@require_POST
def validate_coupon_view(request):
    """Validate a promo/coupon code and return discount info."""
    from subscriptions.models import Coupon
    from decimal import Decimal

    code = (request.POST.get('coupon_code') or '').strip().upper()
    amount_str = request.POST.get('amount', '0')

    if not code:
        return JsonResponse({'ok': False, 'error': 'Please enter a promo code.'})

    try:
        amount = Decimal(amount_str)
    except Exception:
        amount = Decimal('0')

    try:
        coupon = Coupon.objects.get(code=code)
    except Coupon.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Invalid promo code.'})

    can_use, error = coupon.can_use(request.user, amount)
    if not can_use:
        return JsonResponse({'ok': False, 'error': error})

    discount = coupon.calculate_discount(amount)
    return JsonResponse({
        'ok': True,
        'code': coupon.code,
        'discount': str(discount),
        'description': coupon.description or f'{coupon.discount_value}% off',
    })


@login_required
@require_POST
def verify_payment_view(request):
    """
    Verify payment after Razorpay callback.
    """
    from subscriptions.services.payment_service import PaymentService
    from subscriptions.services.subscription_service import SubscriptionService
    import json
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'reason': 'Invalid JSON.'}, status=400)
    
    razorpay_order_id = data.get('razorpay_order_id')
    razorpay_payment_id = data.get('razorpay_payment_id')
    razorpay_signature = data.get('razorpay_signature')
    
    # Verify payment
    result = PaymentService.verify_payment(
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
        razorpay_signature=razorpay_signature
    )
    
    if result['ok']:
        payment = result.get('payment')
        if payment:
            # Activate subscription
            SubscriptionService.sync_after_payment_success(payment)
        
        return JsonResponse({
            'ok': True,
            'reason': 'Payment successful!',
            'redirect': '/dashboard/',
        })
    
    return JsonResponse({'ok': False, 'reason': result.get('reason', 'Payment verification failed.')}, status=400)


@login_required
@require_POST
def cancel_subscription_view(request, subscription_id):
    """
    Cancel a subscription.
    """
    from subscriptions.services.subscription_service import SubscriptionService
    
    try:
        subscription = UserModuleSubscription.objects.get(
            id=subscription_id,
            user=request.user
        )
    except UserModuleSubscription.DoesNotExist:
        messages.error(request, 'Subscription not found.')
        return redirect('my_subscriptions')
    
    reason = request.POST.get('reason', '')
    immediate = request.POST.get('immediate') == 'true'
    
    result = SubscriptionService.cancel(subscription, reason=reason, immediate=immediate)
    
    if result['ok']:
        messages.success(request, f'{subscription.module.name} subscription cancelled.')
    else:
        messages.error(request, result.get('reason', 'Failed to cancel subscription.'))
    
    return redirect('my_subscriptions')


@login_required
def payment_history_view(request):
    """
    Payment history page - shows all user's payments with module, date, and amount.
    """
    payments = Payment.objects.filter(
        user=request.user
    ).select_related().prefetch_related('modules').order_by('-created_at')
    
    context = {
        'payments': payments,
    }
    
    return render(request, 'subscriptions/payment_history.html', context)


@login_required
def bundle_checkout_view(request, bundle_id, pricing_id):
    """Checkout page for purchasing a bundle (all modules at once)."""
    from subscriptions.models import ModuleBundle, BundlePricing

    bundle = get_object_or_404(ModuleBundle, id=bundle_id, is_active=True)
    pricing = get_object_or_404(BundlePricing, id=pricing_id, bundle=bundle, is_active=True)
    bundle_modules = bundle.modules.filter(is_active=True).order_by('display_order')
    all_plans = bundle.bundle_pricing.filter(is_active=True).order_by('duration_months')

    context = {
        'bundle': bundle,
        'pricing': pricing,
        'bundle_modules': bundle_modules,
        'all_plans': all_plans,
    }
    return render(request, 'subscriptions/bundle_checkout.html', context)


@login_required
@require_POST
def create_bundle_order_view(request):
    """Create a Razorpay order for a bundle purchase."""
    from subscriptions.services.payment_service import PaymentService
    from subscriptions.models import BundlePricing

    pricing_id = request.POST.get('pricing_id')
    coupon_code = request.POST.get('coupon_code', '').strip() or None

    try:
        pricing = BundlePricing.objects.select_related('bundle').get(id=pricing_id, is_active=True)
    except BundlePricing.DoesNotExist:
        return JsonResponse({'ok': False, 'reason': 'Invalid bundle pricing.'}, status=400)

    bundle = pricing.bundle
    module_codes = list(bundle.modules.filter(is_active=True).values_list('code', flat=True))
    if not module_codes:
        return JsonResponse({'ok': False, 'reason': 'No modules in this bundle.'}, status=400)

    # Use PaymentService.create_order but with the bundle's own price
    result = PaymentService.create_bundle_order(
        user=request.user,
        bundle=bundle,
        bundle_pricing=pricing,
        coupon_code=coupon_code,
    )

    if result['ok']:
        data = result.get('data', {})
        return JsonResponse({
            'ok': True,
            'order_id': data.get('razorpay_order_id'),
            'internal_order_id': data.get('order_id'),
            'amount': data.get('amount'),
            'currency': data.get('currency', 'INR'),
            'key': data.get('razorpay_key_id'),
            'prefill': {
                'name': data.get('user_name', ''),
                'email': data.get('user_email', ''),
            }
        })

    return JsonResponse({'ok': False, 'reason': result.get('reason', 'Failed to create order.')}, status=400)


@login_required
@require_GET
def trial_status_api(request):
    """
    API endpoint to get trial countdown status for all active trials.
    Returns seconds remaining for each active trial subscription.
    """
    trials = UserModuleSubscription.objects.filter(
        user=request.user,
        status='trial',
        expires_at__gt=timezone.now()
    ).select_related('module')
    
    trial_data = []
    for trial in trials:
        remaining = (trial.expires_at - timezone.now()).total_seconds()
        trial_data.append({
            'module_code': trial.module.code,
            'module_name': trial.module.name,
            'expires_at': trial.expires_at.isoformat(),
            'seconds_remaining': max(0, int(remaining)),
            'usage_count': trial.usage_count,
            'usage_limit': trial.usage_limit,
        })
    
    return JsonResponse({'ok': True, 'trials': trial_data})
