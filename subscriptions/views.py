# subscriptions/views.py
"""
Subscription views for pricing, checkout, and subscription management.
"""

from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from subscriptions.models import Module, ModulePricing, UserModuleSubscription, Payment


@login_required
def module_access_view(request, module_code):
    """
    Module access page - shows trial/subscription options.
    Auto-starts free trial if user has never used this module.
    Users can view this page even if they have trial access (to upgrade).
    Admins/superusers can view the page to see pricing options.
    """
    from subscriptions.services.subscription_service import SubscriptionService
    
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
    
    # Check if user has never used this module - auto-start trial
    has_any_subscription = UserModuleSubscription.objects.filter(
        user=request.user,
        module=module
    ).exists()
    
    if not has_any_subscription:
        # Auto-start the free trial
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
                redirect_url = request.session.pop('subscription_redirect', None)
                if redirect_url:
                    return redirect(redirect_url)
                return redirect('dashboard')
        except Exception as e:
            # Log error but continue to show pricing page
            pass
    
    # Check current subscription status (for display)
    current_sub = UserModuleSubscription.objects.filter(
        user=request.user,
        module=module,
        status__in=['active', 'trial'],
        expires_at__gt=timezone.now()
    ).first()
    
    # Check if trial available (never used trial before)
    trial_available = not UserModuleSubscription.objects.filter(
        user=request.user,
        module=module,
        status='trial'
    ).exists()
    
    # Get pricing options
    plans = ModulePricing.objects.filter(
        module=module,
        is_active=True
    ).order_by('duration_months')
    
    # Reason for access denial
    reason = request.GET.get('reason', 'You need an active subscription to access this module.')
    
    context = {
        'module': module,
        'trial_available': trial_available,
        'trial_days': 1,  # 1 day free trial
        'plans': plans,
        'reason': reason,
        'current_subscription': current_sub,  # Show current trial/subscription status
    }
    
    return render(request, 'subscriptions/module_access.html', context)


@login_required
@require_POST
def start_trial_view(request, module_code):
    """
    Start a free trial for a module.
    """
    module = get_object_or_404(Module, code=module_code, is_active=True)
    
    # Check if user already used trial
    existing_trial = UserModuleSubscription.objects.filter(
        user=request.user,
        module=module,
        status='trial'
    ).exists()
    
    if existing_trial:
        messages.error(request, f'You have already used your free trial for {module.name}.')
        return redirect('module_access', module_code=module_code)
    
    # Check if user already has active subscription
    active_sub = UserModuleSubscription.objects.filter(
        user=request.user,
        module=module,
        status='active',
        expires_at__gt=timezone.now()
    ).first()
    
    if active_sub:
        messages.info(request, f'You already have an active subscription for {module.name}.')
        redirect_url = request.session.pop('subscription_redirect', None)
        if redirect_url:
            return redirect(redirect_url)
        return redirect('dashboard')
    
    # Create 1-day trial subscription
    trial_expires = timezone.now() + timedelta(days=1)
    
    UserModuleSubscription.objects.create(
        user=request.user,
        module=module,
        status='trial',
        started_at=timezone.now(),
        expires_at=trial_expires,
        usage_limit=0,  # Unlimited during trial
    )
    
    messages.success(request, f'🎉 Your 1-day free trial for {module.name} is now active!')
    
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
