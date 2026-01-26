# subscriptions/services/subscription_service.py
"""
Subscription management service - access control, usage, renewal, expiration.
"""

import logging
from datetime import timedelta
from typing import Optional, List
from django.utils import timezone
from django.db.models import Q

logger = logging.getLogger(__name__)


class SubscriptionService:
    """
    Subscription lifecycle management.
    
    Usage:
        result = SubscriptionService.check_access(user, 'estimate')
        result = SubscriptionService.record_usage(user, 'estimate', 'generate')
        result = SubscriptionService.get_user_subscriptions(user)
    """
    
    # =========================================================================
    # ACCESS CONTROL
    # =========================================================================
    
    @classmethod
    def check_access(cls, user, module_code: str) -> dict:
        """
        Check if user has access to a module.
        
        Args:
            user: Django User object
            module_code: Module code (e.g., 'estimate', 'workslip')
        
        Returns:
            {ok: bool, reason: str, data: {subscription, is_trial, days_remaining, usage}}
        """
        from subscriptions.models import Module, UserModuleSubscription
        
        # Check if module exists
        try:
            module = Module.objects.get(code=module_code)
        except Module.DoesNotExist:
            return cls._fail("Module not found.", code="MODULE_NOT_FOUND")
        
        # Free modules - always accessible
        if module.is_free:
            return cls._success(
                "Access granted (free module).",
                data={"is_free": True, "module": module_code}
            )
        
        # Get active subscription
        subscription = UserModuleSubscription.objects.filter(
            user=user,
            module=module,
            status__in=['active', 'trial'],
            expires_at__gt=timezone.now()
        ).first()
        
        if not subscription:
            # Check if trial available
            has_used_trial = UserModuleSubscription.objects.filter(
                user=user,
                module=module,
                status='trial'
            ).exists()
            
            return cls._fail(
                "No active subscription for this module.",
                code="NO_SUBSCRIPTION",
                data={
                    "module": module_code,
                    "trial_available": not has_used_trial,
                    "trial_days": module.trial_days,
                }
            )
        
        # Check usage limit
        can_use, usage_error = subscription.can_use()
        if not can_use:
            return cls._fail(
                usage_error,
                code="USAGE_LIMIT",
                data={
                    "module": module_code,
                    "usage_count": subscription.usage_count,
                    "usage_limit": subscription.usage_limit,
                }
            )
        
        return cls._success(
            "Access granted.",
            data={
                "subscription_id": str(subscription.id),
                "module": module_code,
                "is_trial": subscription.is_trial(),
                "status": subscription.status,
                "days_remaining": subscription.days_remaining(),
                "expires_at": subscription.expires_at.isoformat(),
                "usage_count": subscription.usage_count,
                "usage_limit": subscription.usage_limit,
                "auto_renew": subscription.auto_renew,
            }
        )
    
    @classmethod
    def has_access(cls, user, module_code: str) -> bool:
        """Simple boolean check for access."""
        result = cls.check_access(user, module_code)
        return result['ok']
    
    # =========================================================================
    # USAGE TRACKING
    # =========================================================================
    
    @classmethod
    def record_usage(
        cls,
        user,
        module_code: str,
        action: str,
        resource_id: str = '',
        metadata: Optional[dict] = None,
        request=None
    ) -> dict:
        """
        Record module usage and increment counter.
        
        Args:
            user: Django User object
            module_code: Module code
            action: Action performed (e.g., 'generate_estimate', 'download_pdf')
            resource_id: ID of resource created/modified
            metadata: Additional context
            request: HTTP request for IP/UA tracking
        
        Returns:
            {ok: bool, reason: str, data: {usage_count, usage_remaining}}
        """
        from subscriptions.models import Module, UserModuleSubscription, UsageLog
        
        # Get module
        try:
            module = Module.objects.get(code=module_code)
        except Module.DoesNotExist:
            return cls._fail("Module not found.", code="MODULE_NOT_FOUND")
        
        # Get subscription
        subscription = UserModuleSubscription.objects.filter(
            user=user,
            module=module,
            status__in=['active', 'trial'],
            expires_at__gt=timezone.now()
        ).first()
        
        if subscription:
            # Check limit before recording
            if subscription.usage_limit > 0:
                if subscription.usage_count >= subscription.usage_limit:
                    return cls._fail(
                        "Monthly usage limit reached.",
                        code="USAGE_LIMIT",
                        data={"usage_count": subscription.usage_count}
                    )
            
            # Increment usage
            subscription.record_usage()
        
        # Log usage (even for free modules)
        UsageLog.log(
            user=user,
            module_code=module_code,
            action=action,
            resource_id=resource_id,
            metadata=metadata,
            request=request
        )
        
        usage_remaining = None
        if subscription and subscription.usage_limit > 0:
            usage_remaining = max(0, subscription.usage_limit - subscription.usage_count)
        
        return cls._success(
            "Usage recorded.",
            data={
                "module": module_code,
                "action": action,
                "usage_count": subscription.usage_count if subscription else 0,
                "usage_remaining": usage_remaining,
            }
        )
    
    # =========================================================================
    # TRIAL MANAGEMENT
    # =========================================================================
    
    @classmethod
    def start_trial(cls, user, module_code: str) -> dict:
        """
        Start a free trial for a module.
        
        Args:
            user: Django User object
            module_code: Module code
        
        Returns:
            {ok: bool, reason: str, data: {subscription_id, expires_at}}
        """
        from subscriptions.models import Module, UserModuleSubscription
        
        # Get module
        try:
            module = Module.objects.get(code=module_code, is_active=True)
        except Module.DoesNotExist:
            return cls._fail("Module not found.", code="MODULE_NOT_FOUND")
        
        if module.is_free:
            return cls._fail("This module is free, no trial needed.", code="FREE_MODULE")
        
        # Check if already used trial
        existing = UserModuleSubscription.objects.filter(
            user=user,
            module=module
        ).first()
        
        if existing:
            if existing.status in ['active', 'trial'] and existing.expires_at > timezone.now():
                return cls._fail(
                    "You already have an active subscription.",
                    code="ALREADY_SUBSCRIBED"
                )
            return cls._fail(
                "Trial already used for this module.",
                code="TRIAL_USED"
            )
        
        # Create trial subscription
        expires_at = timezone.now() + timedelta(days=module.trial_days)
        
        subscription = UserModuleSubscription.objects.create(
            user=user,
            module=module,
            status='trial',
            started_at=timezone.now(),
            expires_at=expires_at,
            usage_limit=module.free_tier_limit,
        )
        
        cls._audit_log(user, "trial_started", {
            "module": module_code,
            "expires_at": expires_at.isoformat(),
        })
        
        return cls._success(
            f"Trial started! Expires in {module.trial_days} days.",
            data={
                "subscription_id": str(subscription.id),
                "module": module_code,
                "trial_days": module.trial_days,
                "expires_at": expires_at.isoformat(),
                "usage_limit": module.free_tier_limit,
            }
        )
    
    # =========================================================================
    # SUBSCRIPTION QUERIES
    # =========================================================================
    
    @classmethod
    def get_user_subscriptions(cls, user, include_expired: bool = False) -> dict:
        """
        Get all subscriptions for a user.
        
        Args:
            user: Django User object
            include_expired: Include expired subscriptions
        
        Returns:
            {ok: bool, data: {active: [...], expired: [...], trial: [...]}}
        """
        from subscriptions.models import UserModuleSubscription
        
        qs = UserModuleSubscription.objects.filter(user=user).select_related('module', 'pricing')
        
        active = []
        trial = []
        expired = []
        
        for sub in qs:
            data = {
                "subscription_id": str(sub.id),
                "module": sub.module.code,
                "module_name": sub.module.name,
                "status": sub.status,
                "started_at": sub.started_at.isoformat(),
                "expires_at": sub.expires_at.isoformat(),
                "days_remaining": sub.days_remaining(),
                "usage_count": sub.usage_count,
                "usage_limit": sub.usage_limit,
                "auto_renew": sub.auto_renew,
            }
            
            if sub.status == 'trial' and sub.is_active():
                trial.append(data)
            elif sub.is_active():
                active.append(data)
            elif include_expired:
                expired.append(data)
        
        return cls._success(
            "Subscriptions retrieved.",
            data={
                "active": active,
                "trial": trial,
                "expired": expired if include_expired else [],
                "total_active": len(active) + len(trial),
            }
        )
    
    @classmethod
    def get_available_modules(cls, user) -> dict:
        """
        Get all modules with user's subscription status.
        
        Returns:
            {ok: bool, data: {modules: [...]}}
        """
        from subscriptions.models import Module, UserModuleSubscription
        
        modules = Module.objects.filter(is_active=True).prefetch_related('pricing_options')
        
        # Get user's subscriptions
        user_subs = {}
        for sub in UserModuleSubscription.objects.filter(user=user):
            user_subs[sub.module_id] = sub
        
        result = []
        for module in modules:
            sub = user_subs.get(module.id)
            
            # Determine access status
            if module.is_free:
                access_status = 'free'
            elif sub and sub.is_active():
                access_status = 'subscribed' if sub.status == 'active' else 'trial'
            elif sub:
                access_status = 'expired'
            else:
                access_status = 'available'
            
            # Get pricing
            pricing = []
            for p in module.pricing_options.filter(is_active=True):
                pricing.append({
                    "duration_months": p.duration_months,
                    "duration_label": p.get_duration_months_display(),
                    "base_price": str(p.base_price),
                    "sale_price": str(p.sale_price),
                    "discount_percent": p.discount_percent,
                    "is_popular": p.is_popular,
                })
            
            result.append({
                "code": module.code,
                "name": module.name,
                "description": module.description,
                "icon": module.icon,
                "color": module.color,
                "features": module.features,
                "is_free": module.is_free,
                "trial_days": module.trial_days,
                "access_status": access_status,
                "subscription": {
                    "id": str(sub.id) if sub else None,
                    "status": sub.status if sub else None,
                    "expires_at": sub.expires_at.isoformat() if sub else None,
                    "days_remaining": sub.days_remaining() if sub else None,
                } if sub else None,
                "pricing": pricing,
            })
        
        return cls._success(
            "Modules retrieved.",
            data={"modules": result}
        )
    
    # =========================================================================
    # RENEWAL & EXPIRATION
    # =========================================================================
    
    @classmethod
    def check_expiring_subscriptions(cls, days_ahead: int = 7) -> dict:
        """
        Get subscriptions expiring within N days (for reminder emails).
        
        Args:
            days_ahead: Number of days to look ahead
        
        Returns:
            {ok: bool, data: {subscriptions: [...]}}
        """
        from subscriptions.models import UserModuleSubscription
        
        cutoff = timezone.now() + timedelta(days=days_ahead)
        
        expiring = UserModuleSubscription.objects.filter(
            status__in=['active', 'trial'],
            expires_at__lte=cutoff,
            expires_at__gt=timezone.now(),
            renewal_reminder_sent=False,
        ).select_related('user', 'module')
        
        result = []
        for sub in expiring:
            result.append({
                "subscription_id": str(sub.id),
                "user_id": sub.user.id,
                "user_email": sub.user.email,
                "user_name": sub.user.get_full_name(),
                "module": sub.module.code,
                "module_name": sub.module.name,
                "expires_at": sub.expires_at.isoformat(),
                "days_remaining": sub.days_remaining(),
                "is_trial": sub.is_trial(),
            })
        
        return cls._success(
            f"Found {len(result)} expiring subscriptions.",
            data={"subscriptions": result}
        )
    
    @classmethod
    def mark_reminder_sent(cls, subscription_id: str) -> dict:
        """Mark renewal reminder as sent."""
        from subscriptions.models import UserModuleSubscription
        
        try:
            sub = UserModuleSubscription.objects.get(id=subscription_id)
            sub.renewal_reminder_sent = True
            sub.save(update_fields=['renewal_reminder_sent'])
            return cls._success("Reminder marked as sent.")
        except UserModuleSubscription.DoesNotExist:
            return cls._fail("Subscription not found.", code="NOT_FOUND")
    
    @classmethod
    def expire_subscriptions(cls) -> dict:
        """
        Expire all subscriptions past their expiry date.
        Run this as a scheduled task (e.g., daily via Celery).
        
        Returns:
            {ok: bool, data: {expired_count: int}}
        """
        from subscriptions.models import UserModuleSubscription
        
        expired = UserModuleSubscription.objects.filter(
            status__in=['active', 'trial'],
            expires_at__lt=timezone.now()
        )
        
        count = expired.count()
        expired.update(status='expired')
        
        logger.info(f"Expired {count} subscriptions")
        
        return cls._success(
            f"Expired {count} subscriptions.",
            data={"expired_count": count}
        )
    
    @classmethod
    def reset_monthly_usage(cls) -> dict:
        """
        Reset monthly usage counters.
        Run this on 1st of each month via Celery.
        
        Returns:
            {ok: bool, data: {reset_count: int}}
        """
        from subscriptions.models import UserModuleSubscription
        
        active = UserModuleSubscription.objects.filter(
            status__in=['active', 'trial'],
            usage_limit__gt=0
        )
        
        count = active.count()
        active.update(usage_count=0, usage_reset_at=timezone.now())
        
        logger.info(f"Reset usage for {count} subscriptions")
        
        return cls._success(
            f"Reset usage for {count} subscriptions.",
            data={"reset_count": count}
        )
    
    # =========================================================================
    # CANCELLATION
    # =========================================================================
    
    @classmethod
    def cancel_subscription(cls, user, subscription_id: str) -> dict:
        """
        Cancel a subscription (remains active until expiry).
        
        Args:
            user: Django User object
            subscription_id: Subscription UUID
        
        Returns:
            {ok: bool, reason: str}
        """
        from subscriptions.models import UserModuleSubscription
        
        try:
            sub = UserModuleSubscription.objects.get(id=subscription_id, user=user)
        except UserModuleSubscription.DoesNotExist:
            return cls._fail("Subscription not found.", code="NOT_FOUND")
        
        if sub.status in ['cancelled', 'expired']:
            return cls._fail("Subscription already cancelled/expired.", code="ALREADY_CANCELLED")
        
        sub.cancel()
        
        cls._audit_log(user, "subscription_cancelled", {
            "subscription_id": subscription_id,
            "module": sub.module.code,
            "expires_at": sub.expires_at.isoformat(),
        })
        
        return cls._success(
            f"Subscription cancelled. Access continues until {sub.expires_at.strftime('%B %d, %Y')}.",
            data={
                "subscription_id": subscription_id,
                "expires_at": sub.expires_at.isoformat(),
            }
        )
    
    @classmethod
    def toggle_auto_renew(cls, user, subscription_id: str, enable: bool) -> dict:
        """Toggle auto-renewal for a subscription."""
        from subscriptions.models import UserModuleSubscription
        
        try:
            sub = UserModuleSubscription.objects.get(id=subscription_id, user=user)
        except UserModuleSubscription.DoesNotExist:
            return cls._fail("Subscription not found.", code="NOT_FOUND")
        
        sub.auto_renew = enable
        sub.save(update_fields=['auto_renew'])
        
        return cls._success(
            f"Auto-renewal {'enabled' if enable else 'disabled'}.",
            data={"auto_renew": enable}
        )
    
    # =========================================================================
    # SUBSCRIPTION LIFECYCLE
    # =========================================================================
    
    @classmethod
    def start_subscription(
        cls,
        user,
        module_slugs: List[str],
        plan_term: int = 1,
        payment=None,
        pricing_ids: Optional[List[int]] = None
    ) -> dict:
        """
        Create a new subscription with one or many modules.
        
        Args:
            user: Django User object
            module_slugs: List of module codes ['estimate', 'workslip']
            plan_term: Duration in months (1, 3, 6, 12)
            payment: Optional Payment object to link
            pricing_ids: Optional specific pricing IDs to use
        
        Returns:
            {ok: bool, reason: str, data: {subscription_items: [...]}}
        """
        from subscriptions.models import Module, UserModuleSubscription, ModulePricing
        from django.db import transaction
        
        if not module_slugs:
            return cls._fail("No modules specified.", code="NO_MODULES")
        
        # Validate modules exist
        modules = Module.objects.filter(code__in=module_slugs, is_active=True)
        found_codes = set(m.code for m in modules)
        missing = set(module_slugs) - found_codes
        
        if missing:
            return cls._fail(
                f"Modules not found: {', '.join(missing)}",
                code="INVALID_MODULES"
            )
        
        # Calculate dates
        now = timezone.now()
        expires_at = now + timedelta(days=plan_term * 30)
        
        subscription_items = []
        
        try:
            with transaction.atomic():
                for module in modules:
                    # Get pricing for this module/term
                    pricing = None
                    if pricing_ids:
                        pricing = ModulePricing.objects.filter(
                            id__in=pricing_ids,
                            module=module,
                            duration_months=plan_term,
                            is_active=True
                        ).first()
                    
                    if not pricing:
                        pricing = ModulePricing.objects.filter(
                            module=module,
                            duration_months=plan_term,
                            is_active=True
                        ).first()
                    
                    # Check for existing subscription
                    existing = UserModuleSubscription.objects.filter(
                        user=user,
                        module=module
                    ).first()
                    
                    if existing and existing.is_active():
                        # Extend existing subscription
                        if existing.expires_at > now:
                            existing.expires_at = existing.expires_at + timedelta(days=plan_term * 30)
                        else:
                            existing.expires_at = expires_at
                        existing.status = 'active'
                        existing.pricing = pricing
                        existing.payment = payment
                        existing.save()
                        sub = existing
                    else:
                        # Create new subscription
                        sub = UserModuleSubscription.objects.create(
                            user=user,
                            module=module,
                            pricing=pricing,
                            status='active',
                            started_at=now,
                            expires_at=expires_at,
                            usage_limit=pricing.usage_limit if pricing else 0,
                            payment=payment,
                        )
                    
                    subscription_items.append({
                        "subscription_id": str(sub.id),
                        "module": module.code,
                        "module_name": module.name,
                        "status": sub.status,
                        "started_at": sub.started_at.isoformat(),
                        "expires_at": sub.expires_at.isoformat(),
                        "plan_term_months": plan_term,
                    })
                
                cls._audit_log(user, "subscription_started", {
                    "modules": module_slugs,
                    "plan_term": plan_term,
                    "expires_at": expires_at.isoformat(),
                })
                
                return cls._success(
                    f"Subscription activated for {len(subscription_items)} module(s).",
                    data={
                        "subscription_items": subscription_items,
                        "expires_at": expires_at.isoformat(),
                        "plan_term_months": plan_term,
                    }
                )
                
        except Exception as e:
            logger.error(f"Failed to start subscription: {e}")
            return cls._fail(f"Failed to create subscription: {str(e)}", code="CREATE_ERROR")
    
    @classmethod
    def renew(cls, user, subscription_id: str, plan_term: int = None) -> dict:
        """
        Renew an existing subscription.
        
        Args:
            user: Django User object
            subscription_id: Subscription UUID to renew
            plan_term: New duration in months (None = same as original)
        
        Returns:
            {ok: bool, reason: str, data: {new_expires_at, plan_term}}
        """
        from subscriptions.models import UserModuleSubscription
        
        try:
            sub = UserModuleSubscription.objects.get(id=subscription_id, user=user)
        except UserModuleSubscription.DoesNotExist:
            return cls._fail("Subscription not found.", code="NOT_FOUND")
        
        # Determine plan term
        if plan_term is None:
            if sub.pricing:
                plan_term = sub.pricing.duration_months
            else:
                plan_term = 1  # Default to monthly
        
        # Calculate new expiry
        now = timezone.now()
        if sub.expires_at > now:
            # Add to existing time
            new_expires = sub.expires_at + timedelta(days=plan_term * 30)
        else:
            # Start fresh from now
            new_expires = now + timedelta(days=plan_term * 30)
        
        old_expires = sub.expires_at
        sub.expires_at = new_expires
        sub.status = 'active'
        sub.cancelled_at = None
        sub.cancel_at_period_end = False
        sub.renewal_reminder_sent = False
        sub.save()
        
        cls._audit_log(user, "subscription_renewed", {
            "subscription_id": subscription_id,
            "module": sub.module.code,
            "old_expires": old_expires.isoformat(),
            "new_expires": new_expires.isoformat(),
            "plan_term": plan_term,
        })
        
        return cls._success(
            f"Subscription renewed until {new_expires.strftime('%B %d, %Y')}.",
            data={
                "subscription_id": subscription_id,
                "module": sub.module.code,
                "old_expires_at": old_expires.isoformat(),
                "new_expires_at": new_expires.isoformat(),
                "plan_term_months": plan_term,
            }
        )
    
    @classmethod
    def cancel(cls, user, subscription_id: str, immediate: bool = False) -> dict:
        """
        Cancel a subscription.
        
        Args:
            user: Django User object
            subscription_id: Subscription UUID
            immediate: If True, cancel immediately. If False, cancel at period end.
        
        Returns:
            {ok: bool, reason: str, data: {cancel_at, access_until}}
        """
        from subscriptions.models import UserModuleSubscription
        
        try:
            sub = UserModuleSubscription.objects.get(id=subscription_id, user=user)
        except UserModuleSubscription.DoesNotExist:
            return cls._fail("Subscription not found.", code="NOT_FOUND")
        
        if sub.status in ['cancelled', 'expired']:
            return cls._fail("Subscription already cancelled or expired.", code="ALREADY_CANCELLED")
        
        now = timezone.now()
        
        if immediate:
            # Cancel immediately
            sub.status = 'cancelled'
            sub.cancelled_at = now
            sub.cancel_at_period_end = False
            access_until = now
        else:
            # Cancel at end of billing period
            sub.cancel_at_period_end = True
            sub.cancelled_at = now
            sub.auto_renew = False
            access_until = sub.expires_at
        
        sub.save()
        
        cls._audit_log(user, "subscription_cancelled", {
            "subscription_id": subscription_id,
            "module": sub.module.code,
            "immediate": immediate,
            "access_until": access_until.isoformat(),
        })
        
        if immediate:
            msg = "Subscription cancelled immediately."
        else:
            msg = f"Subscription will be cancelled on {access_until.strftime('%B %d, %Y')}. Access continues until then."
        
        return cls._success(
            msg,
            data={
                "subscription_id": subscription_id,
                "module": sub.module.code,
                "cancelled_at": now.isoformat(),
                "access_until": access_until.isoformat(),
                "immediate": immediate,
            }
        )
    
    @classmethod
    def upgrade_downgrade(
        cls,
        user,
        subscription_id: str,
        new_module_slugs: List[str],
        rule: str = "next_renewal"
    ) -> dict:
        """
        Upgrade or downgrade subscription modules.
        
        Args:
            user: Django User object
            subscription_id: Current subscription to modify
            new_module_slugs: New set of modules
            rule: When to apply change
                  - "next_renewal": Apply at next billing cycle
                  - "immediate": Apply now (may require proration)
        
        Returns:
            {ok: bool, reason: str, data: {effective_at, new_modules}}
        """
        from subscriptions.models import UserModuleSubscription, Module
        
        try:
            current_sub = UserModuleSubscription.objects.get(id=subscription_id, user=user)
        except UserModuleSubscription.DoesNotExist:
            return cls._fail("Subscription not found.", code="NOT_FOUND")
        
        # Validate new modules
        new_modules = Module.objects.filter(code__in=new_module_slugs, is_active=True)
        found_codes = set(m.code for m in new_modules)
        missing = set(new_module_slugs) - found_codes
        
        if missing:
            return cls._fail(
                f"Modules not found: {', '.join(missing)}",
                code="INVALID_MODULES"
            )
        
        now = timezone.now()
        
        if rule == "next_renewal":
            # Schedule change for next renewal
            # Store pending changes in metadata or a separate field
            pending_changes = {
                "new_modules": new_module_slugs,
                "scheduled_at": now.isoformat(),
                "effective_at": current_sub.expires_at.isoformat(),
            }
            
            # Note: This requires a pending_changes JSON field on the model
            # For now, we'll just log it and return the info
            
            cls._audit_log(user, "upgrade_scheduled", {
                "subscription_id": subscription_id,
                "current_module": current_sub.module.code,
                "new_modules": new_module_slugs,
                "effective_at": current_sub.expires_at.isoformat(),
            })
            
            return cls._success(
                f"Module change scheduled for {current_sub.expires_at.strftime('%B %d, %Y')}.",
                data={
                    "subscription_id": subscription_id,
                    "current_module": current_sub.module.code,
                    "new_modules": new_module_slugs,
                    "effective_at": current_sub.expires_at.isoformat(),
                    "rule": rule,
                }
            )
        
        elif rule == "immediate":
            # Apply change immediately
            # Cancel current, create new subscriptions
            remaining_days = (current_sub.expires_at - now).days if current_sub.expires_at > now else 0
            
            # Calculate prorated time to carry forward
            new_expires = now + timedelta(days=remaining_days)
            
            from django.db import transaction
            
            try:
                with transaction.atomic():
                    # Cancel current subscription
                    current_sub.status = 'cancelled'
                    current_sub.cancelled_at = now
                    current_sub.save()
                    
                    # Create new subscriptions with remaining time
                    new_subs = []
                    for module in new_modules:
                        sub, created = UserModuleSubscription.objects.update_or_create(
                            user=user,
                            module=module,
                            defaults={
                                'status': 'active',
                                'started_at': now,
                                'expires_at': new_expires,
                                'pricing': None,  # Will need payment for next term
                            }
                        )
                        new_subs.append({
                            "subscription_id": str(sub.id),
                            "module": module.code,
                            "expires_at": new_expires.isoformat(),
                        })
                    
                    cls._audit_log(user, "upgrade_immediate", {
                        "old_subscription": subscription_id,
                        "old_module": current_sub.module.code,
                        "new_modules": new_module_slugs,
                        "remaining_days": remaining_days,
                    })
                    
                    return cls._success(
                        f"Modules changed immediately. {remaining_days} days carried forward.",
                        data={
                            "old_subscription_id": subscription_id,
                            "new_subscriptions": new_subs,
                            "effective_at": now.isoformat(),
                            "expires_at": new_expires.isoformat(),
                            "days_carried_forward": remaining_days,
                            "rule": rule,
                        }
                    )
            except Exception as e:
                logger.error(f"Upgrade failed: {e}")
                return cls._fail(f"Failed to change modules: {str(e)}", code="UPGRADE_ERROR")
        
        else:
            return cls._fail(f"Invalid rule: {rule}. Use 'next_renewal' or 'immediate'.", code="INVALID_RULE")
    
    @classmethod
    def sync_after_payment_success(cls, payment) -> dict:
        """
        Activate or extend subscriptions based on payment metadata.
        Called after payment is marked successful.
        
        Args:
            payment: Payment model instance with metadata
        
        Returns:
            {ok: bool, reason: str, data: {activated: [...]}}
        """
        from subscriptions.models import Module, UserModuleSubscription, ModulePricing
        
        user = payment.user
        metadata = payment.pricing_snapshot or {}
        modules_data = metadata.get('modules', [])
        
        if not modules_data:
            # Fallback to payment.modules M2M
            if hasattr(payment, 'modules') and payment.modules.exists():
                modules_data = [
                    {'code': m.code, 'duration': 1}
                    for m in payment.modules.all()
                ]
            else:
                return cls._fail("No module information in payment.", code="NO_MODULES")
        
        now = timezone.now()
        activated = []
        
        from django.db import transaction
        
        try:
            with transaction.atomic():
                for module_info in modules_data:
                    module_code = module_info.get('code')
                    duration_months = module_info.get('duration', 1)
                    
                    try:
                        module = Module.objects.get(code=module_code)
                    except Module.DoesNotExist:
                        logger.warning(f"Module not found during sync: {module_code}")
                        continue
                    
                    # Get pricing
                    pricing = ModulePricing.objects.filter(
                        module=module,
                        duration_months=duration_months,
                        is_active=True
                    ).first()
                    
                    # Calculate expiry
                    expires_at = now + timedelta(days=duration_months * 30)
                    
                    # Get or create subscription
                    existing = UserModuleSubscription.objects.filter(
                        user=user,
                        module=module
                    ).first()
                    
                    if existing:
                        # Extend existing
                        if existing.expires_at and existing.expires_at > now:
                            existing.expires_at = existing.expires_at + timedelta(days=duration_months * 30)
                        else:
                            existing.expires_at = expires_at
                        existing.status = 'active'
                        existing.pricing = pricing
                        existing.payment = payment
                        existing.cancel_at_period_end = False
                        existing.cancelled_at = None
                        existing.save()
                        sub = existing
                    else:
                        # Create new
                        sub = UserModuleSubscription.objects.create(
                            user=user,
                            module=module,
                            pricing=pricing,
                            status='active',
                            started_at=now,
                            expires_at=expires_at,
                            usage_limit=pricing.usage_limit if pricing else 0,
                            payment=payment,
                        )
                    
                    activated.append({
                        "subscription_id": str(sub.id),
                        "module": module.code,
                        "module_name": module.name,
                        "expires_at": sub.expires_at.isoformat(),
                        "duration_months": duration_months,
                    })
                
                cls._audit_log(user, "payment_sync_complete", {
                    "payment_id": payment.order_id,
                    "activated_modules": [a['module'] for a in activated],
                })
                
                return cls._success(
                    f"Activated {len(activated)} subscription(s).",
                    data={
                        "payment_id": payment.order_id,
                        "activated": activated,
                    }
                )
                
        except Exception as e:
            logger.error(f"Payment sync failed: {e}")
            return cls._fail(f"Failed to sync subscriptions: {str(e)}", code="SYNC_ERROR")
    
    # =========================================================================
    # RESPONSE BUILDERS
    # =========================================================================
    
    @classmethod
    def _success(cls, reason: str, data: Optional[dict] = None) -> dict:
        return {"ok": True, "reason": reason, "data": data or {}}
    
    @classmethod
    def _fail(cls, reason: str, code: str = "ERROR", data: Optional[dict] = None) -> dict:
        return {"ok": False, "reason": reason, "code": code, "data": data or {}}
    
    @classmethod
    def _audit_log(cls, user, action: str, metadata: dict):
        logger.info(f"[SUBSCRIPTION_AUDIT] {action} | user={user.id} | {metadata}")
