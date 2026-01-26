# subscriptions/services/payment_service.py
"""
Production-ready Payment service with Razorpay integration.

Features:
- Order creation with GST calculation
- Signature verification
- Idempotent webhook handling (replay-safe)
- Refund processing
- Invoice generation

# ---------------------------------------------------------------------------
# TODO: Add these to settings.py for production:
#
# RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', '')
# RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', '')
# RAZORPAY_WEBHOOK_SECRET = os.getenv('RAZORPAY_WEBHOOK_SECRET', '')
# ---------------------------------------------------------------------------
"""

import hmac
import hashlib
import json
import logging
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from django.conf import settings
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


class PaymentService:
    """
    Payment processing with Razorpay.
    
    Usage:
        result = PaymentService.create_order(user, modules, pricing_ids)
        result = PaymentService.verify_payment(order_id, payment_id, signature)
        result = PaymentService.process_refund(payment, amount, reason)
    """
    
    # Razorpay credentials from settings
    RAZORPAY_KEY_ID = getattr(settings, 'RAZORPAY_KEY_ID', '')
    RAZORPAY_KEY_SECRET = getattr(settings, 'RAZORPAY_KEY_SECRET', '')
    
    # Currency
    CURRENCY = 'INR'
    
    # =========================================================================
    # PUBLIC API
    # =========================================================================
    
    @classmethod
    def create_order(
        cls,
        user,
        module_codes: List[str],
        duration_months: int = 1,
        coupon_code: Optional[str] = None
    ) -> dict:
        """
        Create a payment order for module subscriptions.
        
        Args:
            user: Django User object
            module_codes: List of module codes to subscribe
            duration_months: Subscription duration (1, 3, 6, 12)
            coupon_code: Optional coupon code
        
        Returns:
            {ok: bool, reason: str, data: {order_id, razorpay_order_id, amount, ...}}
        """
        from subscriptions.models import Module, ModulePricing, Payment, Coupon
        
        # Validate modules
        modules = Module.objects.filter(code__in=module_codes, is_active=True)
        if not modules.exists():
            return cls._fail("No valid modules selected.", code="INVALID_MODULES")
        
        # Get pricing for each module
        pricing_list = []
        subtotal = Decimal('0.00')
        
        for module in modules:
            pricing = ModulePricing.objects.filter(
                module=module,
                duration_months=duration_months,
                is_active=True
            ).first()
            
            if not pricing:
                return cls._fail(
                    f"Pricing not available for {module.name} ({duration_months} months).",
                    code="PRICING_NOT_FOUND"
                )
            
            pricing_list.append(pricing)
            subtotal += pricing.sale_price
        
        # Apply coupon if provided
        discount_amount = Decimal('0.00')
        coupon = None
        
        if coupon_code:
            try:
                coupon = Coupon.objects.get(code=coupon_code.upper())
                can_use, error = coupon.can_use(user, subtotal)
                if not can_use:
                    return cls._fail(error, code="COUPON_INVALID")
                discount_amount = coupon.calculate_discount(subtotal)
            except Coupon.DoesNotExist:
                return cls._fail("Invalid coupon code.", code="COUPON_NOT_FOUND")
        
        # Calculate totals
        taxable = subtotal - discount_amount
        gst_rate = pricing_list[0].gst_percent if pricing_list else Decimal('18.00')
        gst_amount = (taxable * gst_rate) / 100
        total = taxable + gst_amount
        
        # Create internal order
        order_id = Payment.generate_order_id()
        
        # Create Razorpay order
        razorpay_result = cls._create_razorpay_order(
            amount=total,
            receipt=order_id,
            notes={
                'user_id': str(user.id),
                'modules': ','.join(module_codes),
                'duration': duration_months,
            }
        )
        
        if not razorpay_result['ok']:
            return razorpay_result
        
        razorpay_order_id = razorpay_result['data']['id']
        
        # Create Payment record
        payment = Payment.objects.create(
            order_id=order_id,
            user=user,
            subtotal=subtotal,
            discount_amount=discount_amount,
            gst_amount=gst_amount,
            total_amount=total,
            coupon=coupon,
            gateway='razorpay',
            gateway_order_id=razorpay_order_id,
            billing_name=user.get_full_name(),
            billing_email=user.email,
            pricing_snapshot={
                'modules': [
                    {
                        'code': p.module.code,
                        'name': p.module.name,
                        'duration': p.duration_months,
                        'price': str(p.sale_price),
                    }
                    for p in pricing_list
                ],
                'gst_percent': str(gst_rate),
            }
        )
        payment.modules.set(modules)
        
        cls._audit_log(user, "order_created", {
            "order_id": order_id,
            "amount": str(total),
            "modules": module_codes,
        })
        
        return cls._success(
            "Order created successfully.",
            data={
                "order_id": order_id,
                "razorpay_order_id": razorpay_order_id,
                "razorpay_key_id": cls.RAZORPAY_KEY_ID,
                "amount": int(total * 100),  # Razorpay expects paise
                "amount_display": f"₹{total:,.2f}",
                "currency": cls.CURRENCY,
                "subtotal": str(subtotal),
                "discount": str(discount_amount),
                "gst": str(gst_amount),
                "total": str(total),
                "user_name": user.get_full_name(),
                "user_email": user.email,
                "user_phone": getattr(user, 'phone', ''),
            }
        )
    
    @classmethod
    def verify_payment(
        cls,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str
    ) -> dict:
        """
        Verify Razorpay payment signature and activate subscription.
        
        Args:
            razorpay_order_id: Gateway order ID from Razorpay
            razorpay_payment_id: Payment ID from Razorpay
            razorpay_signature: Signature from Razorpay
        
        Returns:
            {ok: bool, reason: str, data: {subscriptions: [...]}, payment: Payment}
        """
        from subscriptions.models import Payment, UserModuleSubscription, ModulePricing
        
        # Get payment record by gateway_order_id
        try:
            payment = Payment.objects.get(gateway_order_id=razorpay_order_id)
        except Payment.DoesNotExist:
            return cls._fail("Order not found.", code="ORDER_NOT_FOUND")
        
        if payment.status == 'completed':
            # Already completed - return success with payment for subscription sync
            return cls._success("Payment already processed.", data={
                "order_id": payment.order_id,
                "payment": payment,
            })
        
        # Verify signature (skip for mock orders in DEBUG mode)
        if not cls._verify_razorpay_signature(
            razorpay_order_id,
            razorpay_payment_id,
            razorpay_signature
        ):
            payment.mark_failed({'error': 'Signature verification failed'})
            cls._audit_log(payment.user, "payment_failed", {
                "order_id": payment.order_id,
                "reason": "signature_invalid",
            })
            return cls._fail("Payment verification failed.", code="SIGNATURE_INVALID")
        
        # Mark payment as completed
        payment.mark_completed(
            gateway_payment_id=razorpay_payment_id,
            gateway_response={'signature': razorpay_signature}
        )
        payment.gateway_signature = razorpay_signature
        payment.save()
        
        # Record coupon usage
        if payment.coupon:
            payment.coupon.record_use()
        
        # Create subscriptions for each module
        subscriptions = []
        pricing_data = payment.pricing_snapshot.get('modules', [])
        
        for module in payment.modules.all():
            # Find duration from pricing snapshot
            duration = 1
            for p in pricing_data:
                if p['code'] == module.code:
                    duration = p['duration']
                    break
            
            # Get pricing
            pricing = ModulePricing.objects.filter(
                module=module,
                duration_months=duration,
                is_active=True
            ).first()
            
            # Calculate expiry
            expires_at = timezone.now() + timezone.timedelta(days=duration * 30)
            
            # Create subscription
            subscription = UserModuleSubscription.objects.create(
                user=payment.user,
                module=module,
                pricing=pricing,
                status='active',
                started_at=timezone.now(),
                expires_at=expires_at,
                usage_limit=pricing.usage_limit if pricing else 0,
                payment=payment,
            )
            subscriptions.append({
                'module': module.code,
                'module_name': module.name,
                'expires_at': expires_at.isoformat(),
                'subscription_id': str(subscription.id),
            })
        
        # Generate invoice
        cls._generate_invoice(payment)
        
        cls._audit_log(payment.user, "payment_completed", {
            "order_id": payment.order_id,
            "payment_id": razorpay_payment_id,
            "amount": str(payment.total_amount),
            "modules": [m.code for m in payment.modules.all()],
        })
        
        result = cls._success(
            "Payment successful! Subscriptions activated.",
            data={
                "order_id": payment.order_id,
                "payment_id": razorpay_payment_id,
                "subscriptions": subscriptions,
            }
        )
        result['payment'] = payment
        return result
    
    @classmethod
    def process_refund(
        cls,
        order_id: str,
        amount: Optional[Decimal] = None,
        reason: str = ''
    ) -> dict:
        """
        Process refund for a payment.
        
        Args:
            order_id: Internal order ID
            amount: Refund amount (None = full refund)
            reason: Refund reason
        
        Returns:
            {ok: bool, reason: str, data: {refund_id, amount}}
        """
        from subscriptions.models import Payment
        
        try:
            payment = Payment.objects.get(order_id=order_id)
        except Payment.DoesNotExist:
            return cls._fail("Order not found.", code="ORDER_NOT_FOUND")
        
        if payment.status not in ('completed', 'partially_refunded'):
            return cls._fail("Payment cannot be refunded.", code="INVALID_STATUS")
        
        # Default to full refund
        refund_amount = amount or (payment.total_amount - payment.refund_amount)
        
        if refund_amount <= 0:
            return cls._fail("Invalid refund amount.", code="INVALID_AMOUNT")
        
        if refund_amount > (payment.total_amount - payment.refund_amount):
            return cls._fail("Refund amount exceeds available balance.", code="EXCEEDS_BALANCE")
        
        # Process refund via Razorpay
        refund_result = cls._create_razorpay_refund(
            payment.gateway_payment_id,
            refund_amount,
            reason
        )
        
        if not refund_result['ok']:
            return refund_result
        
        # Update payment
        payment.process_refund(refund_amount, reason)
        
        # Cancel subscriptions if full refund
        if payment.status == 'refunded':
            for subscription in payment.subscriptions.all():
                subscription.cancel()
        
        cls._audit_log(payment.user, "refund_processed", {
            "order_id": order_id,
            "amount": str(refund_amount),
            "reason": reason,
        })
        
        return cls._success(
            "Refund processed successfully.",
            data={
                "refund_id": refund_result['data'].get('id'),
                "amount": str(refund_amount),
                "status": payment.status,
            }
        )
    
    @classmethod
    def get_payment_status(cls, order_id: str) -> dict:
        """Get payment status for an order."""
        from subscriptions.models import Payment
        
        try:
            payment = Payment.objects.get(order_id=order_id)
        except Payment.DoesNotExist:
            return cls._fail("Order not found.", code="ORDER_NOT_FOUND")
        
        return cls._success(
            "Payment status retrieved.",
            data={
                "order_id": order_id,
                "status": payment.status,
                "amount": str(payment.total_amount),
                "created_at": payment.created_at.isoformat(),
                "completed_at": payment.completed_at.isoformat() if payment.completed_at else None,
            }
        )
    
    # =========================================================================
    # WEBHOOK HANDLING (IDEMPOTENT)
    # =========================================================================
    
    @classmethod
    def handle_webhook(
        cls,
        payload: bytes,
        headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Handle incoming webhook from Razorpay.
        
        Idempotent: Safe to replay - checks for duplicate events.
        
        Args:
            payload: Raw request body (bytes)
            headers: Request headers dict
        
        Returns:
            {'ok': bool, 'action': str, 'message': str}
        """
        # Step 1: Verify webhook signature
        is_valid, error = cls._verify_webhook_signature(payload, headers)
        if not is_valid:
            logger.warning(f"Webhook signature verification failed: {error}")
            return cls._fail("Signature verification failed", code="INVALID_SIGNATURE")
        
        # Step 2: Parse payload
        try:
            data = json.loads(payload.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"Webhook JSON parse error: {e}")
            return cls._fail("Invalid JSON payload", code="INVALID_JSON")
        
        # Step 3: Extract event info
        event_id = data.get('event', {}).get('id') or data.get('id', '')
        event_type = data.get('event', '') or data.get('type', '')
        
        logger.info(f"Webhook received: {event_type} (event_id: {event_id})")
        
        # Step 4: Idempotency check - skip duplicate events
        if cls._is_duplicate_event(event_id):
            logger.info(f"Duplicate webhook event ignored: {event_id}")
            return cls._success(f"Event {event_id} already processed", data={"action": "DUPLICATE_IGNORED"})
        
        # Step 5: Process event based on type
        try:
            result = cls._process_webhook_event(event_type, data)
            
            # Step 6: Mark event as processed if successful
            if result.get('ok'):
                cls._mark_event_processed(event_id)
            
            return result
            
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            return cls._fail(f"Processing error: {str(e)}", code="PROCESSING_ERROR")
    
    @classmethod
    def _process_webhook_event(cls, event_type: str, data: dict) -> Dict[str, Any]:
        """Process specific webhook event types."""
        from subscriptions.models import Payment
        
        # Payment captured (success)
        if event_type == 'payment.captured':
            return cls._handle_webhook_payment_success(data)
        
        # Payment failed
        elif event_type == 'payment.failed':
            return cls._handle_webhook_payment_failed(data)
        
        # Payment authorized (awaiting capture)
        elif event_type == 'payment.authorized':
            logger.info("Payment authorized, awaiting capture")
            return cls._success("Payment authorized", data={"action": "AUTHORIZED"})
        
        # Refund events
        elif event_type in ('refund.created', 'refund.processed'):
            return cls._handle_webhook_refund(data)
        
        else:
            logger.info(f"Unhandled webhook event type: {event_type}")
            return cls._success(f"Event type {event_type} ignored", data={"action": "IGNORED"})
    
    @classmethod
    def _handle_webhook_payment_success(cls, data: dict) -> Dict[str, Any]:
        """Handle payment.captured webhook."""
        from subscriptions.models import Payment
        
        payload_entity = data.get('payload', {}).get('payment', {}).get('entity', {})
        gateway_order_id = payload_entity.get('order_id', '')
        gateway_payment_id = payload_entity.get('id', '')
        
        if not gateway_order_id:
            return cls._fail("Missing order_id in payload", code="MISSING_ORDER_ID")
        
        try:
            payment = Payment.objects.get(gateway_order_id=gateway_order_id)
        except Payment.DoesNotExist:
            logger.error(f"Payment not found for gateway order: {gateway_order_id}")
            return cls._fail(f"Order {gateway_order_id} not found", code="PAYMENT_NOT_FOUND")
        
        # Idempotency: Skip if already completed
        if payment.status == 'completed':
            logger.info(f"Payment {payment.order_id} already completed")
            return cls._success("Payment already processed", data={"action": "ALREADY_PROCESSED"})
        
        return cls.mark_success(payment, gateway_payment_id)
    
    @classmethod
    def _handle_webhook_payment_failed(cls, data: dict) -> Dict[str, Any]:
        """Handle payment.failed webhook."""
        from subscriptions.models import Payment
        
        payload_entity = data.get('payload', {}).get('payment', {}).get('entity', {})
        gateway_order_id = payload_entity.get('order_id', '')
        error_desc = payload_entity.get('error_description', '')
        error_reason = payload_entity.get('error_reason', 'Payment failed')
        reason = error_desc or error_reason
        
        if not gateway_order_id:
            return cls._fail("Missing order_id in payload", code="MISSING_ORDER_ID")
        
        try:
            payment = Payment.objects.get(gateway_order_id=gateway_order_id)
        except Payment.DoesNotExist:
            return cls._fail(f"Order {gateway_order_id} not found", code="PAYMENT_NOT_FOUND")
        
        # Skip if already failed
        if payment.status == 'failed':
            return cls._success("Payment already marked failed", data={"action": "ALREADY_PROCESSED"})
        
        return cls.mark_failed(payment, reason)
    
    @classmethod
    def _handle_webhook_refund(cls, data: dict) -> Dict[str, Any]:
        """Handle refund webhooks."""
        from subscriptions.models import Payment
        
        payload_entity = data.get('payload', {}).get('refund', {}).get('entity', {})
        payment_id = payload_entity.get('payment_id', '')
        refund_amount = Decimal(payload_entity.get('amount', 0)) / 100  # paise to rupees
        
        try:
            payment = Payment.objects.get(gateway_payment_id=payment_id)
            logger.info(f"Refund webhook for payment {payment.order_id}, amount: {refund_amount}")
            return cls._success("Refund processed via webhook", data={"action": "REFUND_PROCESSED"})
        except Payment.DoesNotExist:
            logger.warning(f"Payment not found for refund: {payment_id}")
            return cls._fail(f"Payment {payment_id} not found", code="PAYMENT_NOT_FOUND")
    
    # =========================================================================
    # STATUS UPDATE METHODS
    # =========================================================================
    
    @classmethod
    @transaction.atomic
    def mark_success(cls, payment, gateway_ref: str) -> Dict[str, Any]:
        """
        Mark payment as successful and activate subscriptions.
        
        Args:
            payment: Payment model instance
            gateway_ref: Gateway's payment/transaction ID
        
        Returns:
            {'ok': bool, 'reason': str, 'data': {...}}
        """
        from subscriptions.models import UserModuleSubscription, ModulePricing
        
        # Update payment status
        payment.mark_completed(
            gateway_payment_id=gateway_ref,
            gateway_response={'webhook': True}
        )
        
        logger.info(f"Payment {payment.order_id} marked SUCCESS (ref: {gateway_ref})")
        
        # Record coupon usage
        if payment.coupon:
            payment.coupon.record_use()
        
        # Activate subscriptions for each module
        subscriptions = []
        pricing_data = payment.pricing_snapshot.get('modules', [])
        
        for module in payment.modules.all():
            # Find duration from pricing snapshot
            duration = 1
            for p in pricing_data:
                if p['code'] == module.code:
                    duration = p['duration']
                    break
            
            # Get pricing
            pricing = ModulePricing.objects.filter(
                module=module,
                duration_months=duration,
                is_active=True
            ).first()
            
            # Calculate expiry
            expires_at = timezone.now() + timezone.timedelta(days=duration * 30)
            
            # Create or update subscription
            subscription, created = UserModuleSubscription.objects.update_or_create(
                user=payment.user,
                module=module,
                defaults={
                    'pricing': pricing,
                    'status': 'active',
                    'started_at': timezone.now(),
                    'expires_at': expires_at,
                    'usage_limit': pricing.usage_limit if pricing else 0,
                    'payment': payment,
                }
            )
            
            subscriptions.append({
                'module': module.code,
                'expires_at': expires_at.isoformat(),
            })
        
        # Generate invoice
        cls._generate_invoice(payment)
        
        cls._audit_log(payment.user, "payment_success_webhook", {
            "order_id": payment.order_id,
            "payment_id": gateway_ref,
            "modules": [m.code for m in payment.modules.all()],
        })
        
        return cls._success(
            "Payment successful",
            data={
                "action": "PAYMENT_SUCCESS",
                "order_id": payment.order_id,
                "subscriptions": subscriptions,
            }
        )
    
    @classmethod
    def mark_failed(cls, payment, reason: str) -> Dict[str, Any]:
        """
        Mark payment as failed.
        
        Args:
            payment: Payment model instance
            reason: Failure reason/error message
        
        Returns:
            {'ok': bool, 'reason': str, 'data': {...}}
        """
        payment.mark_failed({'error': reason, 'source': 'webhook'})
        
        logger.info(f"Payment {payment.order_id} marked FAILED: {reason}")
        
        cls._audit_log(payment.user, "payment_failed_webhook", {
            "order_id": payment.order_id,
            "reason": reason,
        })
        
        return cls._success(
            "Payment marked as failed",
            data={
                "action": "PAYMENT_FAILED",
                "order_id": payment.order_id,
                "reason": reason,
            }
        )
    
    # =========================================================================
    # WEBHOOK SIGNATURE VERIFICATION
    # =========================================================================
    
    @classmethod
    def _verify_webhook_signature(
        cls,
        payload: bytes,
        headers: Dict[str, str]
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify Razorpay webhook signature.
        
        Returns:
            (is_valid: bool, error_message: Optional[str])
        """
        # Get webhook secret from settings
        webhook_secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', '')
        
        # Skip verification in DEBUG mode without secret configured
        if not webhook_secret:
            if settings.DEBUG:
                logger.warning("Webhook signature verification skipped (no secret configured)")
                return True, None
            return False, "Webhook secret not configured"
        
        # Get signature from headers
        signature = headers.get('X-Razorpay-Signature', '')
        if not signature:
            return False, "Missing X-Razorpay-Signature header"
        
        # Compute expected signature
        expected = hmac.new(
            webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Constant-time comparison
        if hmac.compare_digest(expected, signature):
            return True, None
        else:
            return False, "Signature mismatch"
    
    # =========================================================================
    # IDEMPOTENCY / DEDUPLICATION
    # =========================================================================
    
    @classmethod
    def _is_duplicate_event(cls, event_id: str) -> bool:
        """Check if webhook event has already been processed."""
        if not event_id:
            return False
        
        from django.core.cache import cache
        cache_key = f"razorpay_webhook_{event_id}"
        return cache.get(cache_key) is not None
    
    @classmethod
    def _mark_event_processed(cls, event_id: str) -> None:
        """Mark webhook event as processed (TTL: 24 hours)."""
        if not event_id:
            return
        
        from django.core.cache import cache
        cache_key = f"razorpay_webhook_{event_id}"
        cache.set(cache_key, True, 60 * 60 * 24)  # 24 hours
    
    # =========================================================================
    # RAZORPAY API
    # =========================================================================
    
    @classmethod
    def _get_razorpay_client(cls):
        """Get Razorpay client instance."""
        # Check if credentials are properly configured (not empty or placeholder)
        key_id = cls.RAZORPAY_KEY_ID
        key_secret = cls.RAZORPAY_KEY_SECRET
        
        # Return None if credentials are empty or contain placeholders
        if not key_id or not key_secret:
            return None
        if 'XXXX' in key_id or 'your-' in key_secret.lower():
            return None
        if not key_id.startswith(('rzp_test_', 'rzp_live_')):
            return None
        
        try:
            import razorpay
            return razorpay.Client(auth=(key_id, key_secret))
        except ImportError:
            logger.error("razorpay package not installed")
            return None
    
    @classmethod
    def _create_razorpay_order(cls, amount: Decimal, receipt: str, notes: dict) -> dict:
        """Create order on Razorpay."""
        client = cls._get_razorpay_client()
        
        if not client:
            # Fallback for development without Razorpay
            if settings.DEBUG:
                return cls._success("Mock order created.", data={
                    "id": f"order_mock_{receipt}",
                    "amount": int(amount * 100),
                    "currency": cls.CURRENCY,
                })
            return cls._fail("Payment gateway not configured.", code="GATEWAY_ERROR")
        
        try:
            order_data = {
                "amount": int(amount * 100),  # Convert to paise
                "currency": cls.CURRENCY,
                "receipt": receipt,
                "notes": notes,
            }
            order = client.order.create(data=order_data)
            return cls._success("Razorpay order created.", data=order)
        except Exception as e:
            logger.error(f"Razorpay order creation failed: {e}")
            return cls._fail(f"Payment gateway error: {str(e)}", code="GATEWAY_ERROR")
    
    @classmethod
    def _verify_razorpay_signature(
        cls,
        order_id: str,
        payment_id: str,
        signature: str
    ) -> bool:
        """Verify Razorpay payment signature."""
        if settings.DEBUG and order_id.startswith('order_mock_'):
            return True  # Skip verification for mock orders
        
        message = f"{order_id}|{payment_id}"
        expected = hmac.new(
            cls.RAZORPAY_KEY_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)
    
    @classmethod
    def _create_razorpay_refund(cls, payment_id: str, amount: Decimal, reason: str) -> dict:
        """Create refund on Razorpay."""
        client = cls._get_razorpay_client()
        
        if not client:
            if settings.DEBUG:
                return cls._success("Mock refund created.", data={"id": "rfnd_mock"})
            return cls._fail("Payment gateway not configured.", code="GATEWAY_ERROR")
        
        try:
            refund = client.payment.refund(payment_id, {
                "amount": int(amount * 100),
                "notes": {"reason": reason},
            })
            return cls._success("Refund created.", data=refund)
        except Exception as e:
            logger.error(f"Razorpay refund failed: {e}")
            return cls._fail(f"Refund failed: {str(e)}", code="REFUND_ERROR")
    
    # =========================================================================
    # INVOICE GENERATION
    # =========================================================================
    
    @classmethod
    def _generate_invoice(cls, payment) -> None:
        """Generate invoice for completed payment."""
        from subscriptions.models import Invoice
        
        # Build line items
        line_items = []
        for data in payment.pricing_snapshot.get('modules', []):
            line_items.append({
                "module": data['name'],
                "duration": f"{data['duration']} Month(s)",
                "price": data['price'],
            })
        
        # Calculate tax split (simplified - same state = CGST+SGST, else IGST)
        gst = payment.gst_amount
        cgst = sgst = gst / 2
        igst = Decimal('0.00')
        
        Invoice.objects.create(
            invoice_number=Invoice.generate_invoice_number(),
            payment=payment,
            user=payment.user,
            subtotal=payment.subtotal,
            discount_amount=payment.discount_amount,
            taxable_amount=payment.subtotal - payment.discount_amount,
            cgst_amount=cgst,
            sgst_amount=sgst,
            igst_amount=igst,
            total_amount=payment.total_amount,
            line_items=line_items,
            billing_name=payment.billing_name,
            billing_address=payment.billing_address,
            billing_gstin=payment.billing_gstin,
        )
    
    # =========================================================================
    # RESPONSE BUILDERS
    # =========================================================================
    
    @classmethod
    def _success(cls, reason: str, data: Optional[dict] = None) -> dict:
        return {"ok": True, "reason": reason, "data": data or {}}
    
    @classmethod
    def _fail(cls, reason: str, code: str = "ERROR", data: Optional[dict] = None) -> dict:
        return {"ok": False, "reason": reason, "code": code, "data": data or {}}
    
    # =========================================================================
    # AUDIT
    # =========================================================================
    
    @classmethod
    def _audit_log(cls, user, action: str, metadata: dict):
        """Log payment events."""
        logger.info(f"[PAYMENT_AUDIT] {action} | user={user.id} | {metadata}")
