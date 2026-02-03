
# =============================================================================
# MODULE LIST VIEW (FIX FOR MISSING VIEW)
# =============================================================================

from admin_panel.decorators import admin_required, superadmin_required
from subscriptions.models import Module
from accounts.models import UserProfile, UserSession
from subscriptions.models import ModulePricing, UserModuleSubscription, Payment
from support.models import SupportTicket, TicketMessage, Announcement, FAQCategory, FAQItem

import json
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.core.paginator import Paginator
from django.db.models import Count, Sum, Q
from django.utils import timezone


@admin_required
def module_list(request):
    """
    List all modules for admin panel.
    """
    modules = Module.objects.all().order_by('display_order', 'name')
    context = {
        'modules': modules,
    }
    return render(request, 'admin_panel/modules/list.html', context)


# =============================================================================
# DASHBOARD
# =============================================================================

@admin_required
def admin_dashboard(request):
    """
    Admin dashboard with key metrics and recent activity.
    """
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # User stats
    total_users = User.objects.filter(is_active=True).count()
    new_users_week = User.objects.filter(date_joined__date__gte=week_ago).count()
    new_users_month = User.objects.filter(date_joined__date__gte=month_ago).count()
    
    # Subscription stats
    active_subs = UserModuleSubscription.objects.filter(
        status='active',
        expires_at__gt=timezone.now()
    ).count()
    trial_subs = UserModuleSubscription.objects.filter(
        status='trial',
        expires_at__gt=timezone.now()
    ).count()
    
    # Revenue stats
    month_revenue = Payment.objects.filter(
        status='success',
        created_at__date__gte=month_ago
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Support stats
    open_tickets = SupportTicket.objects.filter(status__in=['open', 'pending']).count()
    
    # Recent activity
    recent_users = User.objects.order_by('-date_joined')[:5]
    recent_payments = Payment.objects.filter(status='success').order_by('-created_at')[:5]
    recent_tickets = SupportTicket.objects.order_by('-created_at')[:5]
    
    context = {
        'stats': {
            'total_users': total_users,
            'new_users_week': new_users_week,
            'new_users_month': new_users_month,
            'active_subscriptions': active_subs,
            'trial_subscriptions': trial_subs,
            'month_revenue': month_revenue,
            'open_tickets': open_tickets,
        },
        'recent_users': recent_users,
        'recent_payments': recent_payments,
        'recent_tickets': recent_tickets,
    }
    
    return render(request, 'admin_panel/dashboard.html', context)


# =============================================================================
# USER MANAGEMENT
# =============================================================================

@admin_required
def user_list(request):
    """
    List all users with search and filters.
    """
    users = User.objects.select_related('account_profile').order_by('-date_joined')
    
    # Search
    search = request.GET.get('q', '').strip()
    if search:
        users = users.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(account_profile__phone__icontains=search)
        )
    
    # Filter by status
    status = request.GET.get('status')
    if status == 'active':
        users = users.filter(is_active=True)
    elif status == 'inactive':
        users = users.filter(is_active=False)
    
    # Filter by role
    role = request.GET.get('role')
    if role:
        users = users.filter(account_profile__role=role)
    
    # Pagination
    paginator = Paginator(users, 25)
    page = request.GET.get('page', 1)
    users_page = paginator.get_page(page)
    
    context = {
        'users': users_page,
        'search': search,
        'status': status,
        'role': role,
    }
    
    return render(request, 'admin_panel/users/list.html', context)


@admin_required
def user_detail(request, user_id):
    """
    View user details and subscriptions.
    """
    user = get_object_or_404(User, id=user_id)
    profile = getattr(user, 'account_profile', None)
    
    subscriptions = UserModuleSubscription.objects.filter(
        user=user
    ).select_related('module', 'pricing').order_by('-created_at')
    
    payments = Payment.objects.filter(user=user).order_by('-created_at')[:10]
    sessions = UserSession.objects.filter(user=user, is_active=True).order_by('-last_activity')
    
    context = {
        'target_user': user,
        'profile': profile,
        'subscriptions': subscriptions,
        'payments': payments,
        'sessions': sessions,
    }
    
    return render(request, 'admin_panel/users/detail.html', context)


@admin_required
@require_http_methods(["GET", "POST"])
def user_edit(request, user_id):
    """
    Edit user details and role.
    """
    user = get_object_or_404(User, id=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    
    if request.method == 'POST':
        # Update user
        old_data = {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'is_active': user.is_active,
            'phone': profile.phone,
            'company_name': profile.company_name,
            'role': profile.role,
        }
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.is_active = request.POST.get('is_active') == 'on'
        user.save()

        # Update profile
        profile.phone = request.POST.get('phone', profile.phone)
        profile.company_name = request.POST.get('company_name', profile.company_name)
        profile.role = request.POST.get('role', profile.role)
        profile.save()

        # --- AUDIT LOG ---
        from datasets.models import AuditLog
        AuditLog.log(
            user=request.user,
            action='update',
            obj=user,
            changes={
                'before': old_data,
                'after': {
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email,
                    'is_active': user.is_active,
                    'phone': profile.phone,
                    'company_name': profile.company_name,
                    'role': profile.role,
                }
            },
            metadata={'user_id': user.id},
            request=request
        )

        messages.success(request, f'User {user.username} updated successfully.')
        return redirect('admin_user_detail', user_id=user.id)
    
    context = {
        'target_user': user,
        'profile': profile,
        'roles': UserProfile.ROLE_CHOICES,
    }
    
    return render(request, 'admin_panel/users/edit.html', context)


@admin_required
@require_POST
def user_toggle_status(request, user_id):
    """
    Toggle user active status.
    """
    user = get_object_or_404(User, id=user_id)
    
    # Prevent self-deactivation
    if user.id == request.user.id:
        messages.error(request, 'You cannot deactivate your own account.')
        return redirect('admin_user_detail', user_id=user.id)
    
    user.is_active = not user.is_active
    user.save()
    
    status = 'activated' if user.is_active else 'deactivated'
    messages.success(request, f'User {user.username} {status}.')
    
    return redirect('admin_user_detail', user_id=user.id)


@superadmin_required
@require_POST
def user_change_role(request, user_id):
    """
    Change user role (superadmin only).
    Requires password verification for security.
    """
    user = get_object_or_404(User, id=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    
    # Security: Require admin's password for role changes
    admin_password = request.POST.get('admin_password', '')
    if not admin_password:
        messages.error(request, 'Password verification is required to change user roles.')
        return redirect('admin_user_detail', user_id=user.id)
    
    if not request.user.check_password(admin_password):
        messages.error(request, 'Incorrect password. Role change denied for security reasons.')
        # Log failed attempt
        from datasets.models import AuditLog
        AuditLog.log(
            user=request.user,
            action='security_alert',
            obj=user,
            changes={'attempted_action': 'role_change', 'reason': 'incorrect_password'},
            metadata={'target_user_id': user.id},
            request=request
        )
        return redirect('admin_user_detail', user_id=user.id)
    
    # Prevent self-demotion for superadmins (safety measure)
    if user.id == request.user.id:
        messages.warning(request, 'You cannot change your own role. Ask another superadmin.')
        return redirect('admin_user_detail', user_id=user.id)

    old_role = profile.role
    new_role = request.POST.get('role')
    if new_role in dict(UserProfile.ROLE_CHOICES):
        profile.role = new_role
        profile.save()
        
        # Update Django staff/superuser status based on role
        if new_role == 'superadmin':
            user.is_staff = True
            user.is_superuser = True
        elif new_role == 'admin':
            user.is_staff = True
            user.is_superuser = False
        else:
            user.is_staff = False
            user.is_superuser = False
        user.save()
        
        # --- AUDIT LOG ---
        from datasets.models import AuditLog
        AuditLog.log(
            user=request.user,
            action='update',
            obj=user,
            changes={
                'before': {'role': old_role},
                'after': {'role': new_role},
            },
            metadata={'user_id': user.id, 'security_verified': True},
            request=request
        )
        messages.success(request, f'User {user.username} role changed from {old_role} to {new_role}.')
    else:
        messages.error(request, 'Invalid role.')

    return redirect('admin_user_detail', user_id=user.id)


# =============================================================================
# MODULE MANAGEMENT
# =============================================================================



@admin_required
@require_http_methods(["GET", "POST"])
def module_edit(request, module_id=0):
    """
    Create or edit a module.
    """
    if module_id:
        module = get_object_or_404(Module, id=module_id)
    else:
        module = None
    
    if request.method == 'POST':
        code = request.POST.get('code', '').strip().lower()
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        url_name = request.POST.get('url_name', '').strip()
        icon = request.POST.get('icon', '').strip()
        color = request.POST.get('color', '#3B82F6')
        display_order = int(request.POST.get('display_order', 0))
        is_active = request.POST.get('is_active') == 'on'
        is_free = request.POST.get('is_free') == 'on'
        trial_days = int(request.POST.get('trial_days', 7))
        free_tier_limit = int(request.POST.get('free_tier_limit', 5))
        features = request.POST.get('features', '')
        backend_sheet_name = request.POST.get('backend_sheet_name', '').strip()
        
        # Parse features as JSON array
        try:
            features_list = json.loads(features) if features else []
        except json.JSONDecodeError:
            features_list = [f.strip() for f in features.split('\n') if f.strip()]
        
        if module:
            module.code = code
            module.name = name
            module.description = description
            module.url_name = url_name
            module.icon = icon
            module.color = color
            module.display_order = display_order
            module.is_active = is_active
            module.is_free = is_free
            module.trial_days = trial_days
            module.free_tier_limit = free_tier_limit
            module.features = features_list
            module.backend_sheet_name = backend_sheet_name
            
            # Handle backend sheet file upload
            if 'backend_sheet_file' in request.FILES:
                module.backend_sheet_file = request.FILES['backend_sheet_file']
            
            module.save()
            messages.success(request, f'Module "{name}" updated.')
        else:
            module = Module.objects.create(
                code=code,
                name=name,
                description=description,
                url_name=url_name,
                icon=icon,
                color=color,
                display_order=display_order,
                is_active=is_active,
                is_free=is_free,
                trial_days=trial_days,
                free_tier_limit=free_tier_limit,
                features=features_list,
                backend_sheet_name=backend_sheet_name,
            )
            # Handle backend sheet file upload for new module
            if 'backend_sheet_file' in request.FILES:
                module.backend_sheet_file = request.FILES['backend_sheet_file']
                module.save()
            
            messages.success(request, f'Module "{name}" created.')
        
        return redirect('admin_module_list')
    
    context = {
        'module': module,
    }
    
    return render(request, 'admin_panel/modules/edit.html', context)


@admin_required
@require_http_methods(["GET", "POST"])
def pricing_edit(request, module_id, pricing_id=None):
    """
    Edit all pricing tiers for a module at once.
    """
    module = get_object_or_404(Module, id=module_id)
    
    # Get existing pricing for all durations
    existing_pricing = {p.duration_months: p for p in module.pricing_options.all()}
    
    # Define the tiers we want to manage
    pricing_tiers = [
        {'months': 1, 'name': 'Monthly', 'icon': 'calendar-month'},
        {'months': 3, 'name': 'Quarterly', 'icon': 'calendar3'},
        {'months': 6, 'name': 'Half-Yearly', 'icon': 'calendar-range'},
        {'months': 12, 'name': 'Yearly', 'icon': 'calendar-check'},
    ]
    
    if request.method == 'POST':
        from decimal import Decimal
        
        # Process each tier
        for tier in pricing_tiers:
            months = tier['months']
            prefix = f'tier_{months}_'
            
            # Check if this tier is enabled
            is_enabled = request.POST.get(f'{prefix}enabled') == 'on'
            
            if is_enabled:
                base_price = Decimal(request.POST.get(f'{prefix}base_price', '0') or '0')
                sale_price = Decimal(request.POST.get(f'{prefix}sale_price', '0') or '0')
                gst_percent = Decimal(request.POST.get(f'{prefix}gst_percent', '18') or '18')
                usage_limit = int(request.POST.get(f'{prefix}usage_limit', '0') or '0')
                is_popular = request.POST.get(f'{prefix}is_popular') == 'on'
                
                # Update or create pricing for this tier
                ModulePricing.objects.update_or_create(
                    module=module,
                    duration_months=months,
                    defaults={
                        'base_price': base_price,
                        'sale_price': sale_price if sale_price > 0 else base_price,
                        'gst_percent': gst_percent,
                        'usage_limit': usage_limit,
                        'is_active': True,
                        'is_popular': is_popular,
                    }
                )
            else:
                # Disable this tier if it exists
                ModulePricing.objects.filter(module=module, duration_months=months).update(is_active=False)
        
        messages.success(request, f'Pricing updated for {module.name}.')
        return redirect('admin_module_list')
    
    # Prepare tier data for template
    tiers_data = []
    for tier in pricing_tiers:
        months = tier['months']
        existing = existing_pricing.get(months)
        tiers_data.append({
            'months': months,
            'name': tier['name'],
            'icon': tier['icon'],
            'pricing': existing,
            'is_enabled': existing.is_active if existing else False,
            'base_price': existing.base_price if existing else 0,
            'sale_price': existing.sale_price if existing else 0,
            'gst_percent': existing.gst_percent if existing else 18,
            'usage_limit': existing.usage_limit if existing else 0,
            'is_popular': existing.is_popular if existing else False,
        })
    
    context = {
        'module': module,
        'tiers': tiers_data,
    }
    
    return render(request, 'admin_panel/modules/pricing_edit.html', context)


# =============================================================================
# SUBSCRIPTION MANAGEMENT
# =============================================================================

@admin_required
def subscription_list(request):
    """
    List all subscriptions grouped by user.
    """
    from collections import OrderedDict
    
    subs = UserModuleSubscription.objects.select_related(
        'user', 'module', 'pricing'
    ).order_by('user__username', '-created_at')
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        subs = subs.filter(status=status)
    
    # Filter by module
    module_id = request.GET.get('module')
    if module_id:
        subs = subs.filter(module_id=module_id)
    
    # Search by user
    search = request.GET.get('q', '').strip()
    if search:
        subs = subs.filter(
            Q(user__username__icontains=search) |
            Q(user__email__icontains=search)
        )
    
    # Group subscriptions by user
    users_with_subs = OrderedDict()
    for sub in subs:
        user_id = sub.user.id
        if user_id not in users_with_subs:
            users_with_subs[user_id] = {
                'user': sub.user,
                'subscriptions': [],
                'active_count': 0,
                'trial_count': 0,
                'expired_count': 0,
            }
        users_with_subs[user_id]['subscriptions'].append(sub)
        if sub.status == 'active':
            users_with_subs[user_id]['active_count'] += 1
        elif sub.status == 'trial':
            users_with_subs[user_id]['trial_count'] += 1
        elif sub.status == 'expired':
            users_with_subs[user_id]['expired_count'] += 1
    
    # Pagination on users
    user_list = list(users_with_subs.values())
    paginator = Paginator(user_list, 15)
    page = request.GET.get('page', 1)
    users_page = paginator.get_page(page)
    
    modules = Module.objects.filter(is_active=True)
    total_subs = subs.count()
    
    context = {
        'users_with_subs': users_page,
        'total_subs': total_subs,
        'modules': modules,
        'status': status,
        'module_id': module_id,
        'search': search,
    }
    
    return render(request, 'admin_panel/subscriptions/list.html', context)


@admin_required
@require_http_methods(["GET", "POST"])
def grant_subscription(request, user_id):
    """
    Grant subscriptions to a user manually.
    Supports granting trial or full access to individual modules or all modules at once.
    """
    user = get_object_or_404(User, id=user_id)
    modules = Module.objects.filter(is_active=True).order_by('display_order', 'name')
    
    # Get selected module from query param for pre-selection
    selected_module = request.GET.get('module', '')
    
    # Get user's existing subscriptions for display
    existing_subs = {
        sub.module_id: sub 
        for sub in UserModuleSubscription.objects.filter(
            user=user,
            status__in=['active', 'trial'],
            expires_at__gt=timezone.now()
        )
    }
    
    if request.method == 'POST':
        access_type = request.POST.get('access_type', 'full')  # 'trial' or 'full'
        module_selection = request.POST.get('module_selection', 'individual')  # 'individual' or 'all'
        selected_module_ids = request.POST.getlist('modules')  # List of module IDs
        
        # Handle duration
        if access_type == 'trial':
            # Trial duration
            trial_duration = request.POST.get('trial_duration', '1')
            if trial_duration == 'custom':
                duration_days = int(request.POST.get('trial_custom_days', 1))
            else:
                duration_days = int(trial_duration)
            status = 'trial'
        else:
            # Full access duration
            full_duration = request.POST.get('full_duration', '30')
            if full_duration == 'custom':
                duration_days = int(request.POST.get('full_custom_days', 30))
            else:
                duration_days = int(full_duration)
            status = 'active'
        
        reason = request.POST.get('note', '')
        
        # Determine which modules to grant
        if module_selection == 'all':
            modules_to_grant = modules
        else:
            modules_to_grant = Module.objects.filter(id__in=selected_module_ids, is_active=True)
        
        if not modules_to_grant.exists():
            messages.error(request, 'Please select at least one module.')
            return redirect('admin_grant_subscription', user_id=user.id)
        
        granted_count = 0
        extended_count = 0
        
        for module in modules_to_grant:
            # Check for existing subscription
            existing = UserModuleSubscription.objects.filter(
                user=user,
                module=module,
                status__in=['active', 'trial'],
                expires_at__gt=timezone.now()
            ).first()
            
            if existing:
                # Extend existing
                existing.expires_at = existing.expires_at + timedelta(days=duration_days)
                existing.status = status  # Update status if changing from trial to full
                existing.save()
                extended_count += 1
            else:
                # Create new
                UserModuleSubscription.objects.create(
                    user=user,
                    module=module,
                    status=status,
                    started_at=timezone.now(),
                    expires_at=timezone.now() + timedelta(days=duration_days),
                )
                granted_count += 1
        
        access_label = 'Trial' if access_type == 'trial' else 'Full Access'
        
        if granted_count > 0 and extended_count > 0:
            messages.success(
                request, 
                f'Granted {access_label} for {granted_count} module(s) and extended {extended_count} existing subscription(s) by {duration_days} days.'
            )
        elif granted_count > 0:
            messages.success(
                request, 
                f'Granted {access_label} for {granted_count} module(s) for {duration_days} days.'
            )
        elif extended_count > 0:
            messages.success(
                request, 
                f'Extended {extended_count} existing subscription(s) by {duration_days} days.'
            )
        
        return redirect('admin_user_detail', user_id=user.id)
    
    # Prepare modules with existing subscription info
    modules_with_status = []
    for module in modules:
        existing_sub = existing_subs.get(module.id)
        modules_with_status.append({
            'module': module,
            'has_subscription': existing_sub is not None,
            'subscription': existing_sub,
            'status': existing_sub.status if existing_sub else None,
            'expires_at': existing_sub.expires_at if existing_sub else None,
            'days_remaining': existing_sub.days_remaining() if existing_sub else 0,
        })
    
    context = {
        'target_user': user,
        'modules': modules,
        'modules_with_status': modules_with_status,
        'selected_module': selected_module,
        'existing_subs': existing_subs,
    }
    
    return render(request, 'admin_panel/subscriptions/grant.html', context)


@admin_required
@require_POST
def revoke_subscription(request, subscription_id):
    """
    Revoke/cancel a subscription.
    """
    sub = get_object_or_404(UserModuleSubscription, id=subscription_id)
    
    sub.status = 'cancelled'
    sub.cancelled_at = timezone.now()
    sub.save()
    
    messages.success(request, f'Subscription revoked for {sub.user.username}.')
    
    return redirect('admin_subscription_list')


# =============================================================================
# SUPPORT TICKET MANAGEMENT
# =============================================================================

@admin_required
def ticket_list(request):
    """
    List all support tickets.
    """
    tickets = SupportTicket.objects.select_related('user').order_by('-updated_at')
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        tickets = tickets.filter(status=status)
    
    # Filter by priority
    priority = request.GET.get('priority')
    if priority:
        tickets = tickets.filter(priority=priority)
    
    # Search
    search = request.GET.get('q', '').strip()
    if search:
        tickets = tickets.filter(
            Q(subject__icontains=search) |
            Q(user__username__icontains=search) |
            Q(ticket_number__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(tickets, 25)
    page = request.GET.get('page', 1)
    tickets_page = paginator.get_page(page)
    
    context = {
        'tickets': tickets_page,
        'status': status,
        'priority': priority,
        'search': search,
    }
    
    return render(request, 'admin_panel/tickets/list.html', context)


@admin_required
def ticket_detail(request, ticket_id):
    """
    View ticket details and reply.
    """
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    ticket_messages = ticket.messages.order_by('created_at')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'reply':
            message = request.POST.get('message', '').strip()
            if message:
                TicketMessage.objects.create(
                    ticket=ticket,
                    sender=request.user,
                    message=message,
                    is_admin_reply=True,
                )
                ticket.status = 'in_progress'
                ticket.save()
                messages.success(request, 'Reply sent.')
        
        elif action == 'close':
            ticket.status = 'closed'
            ticket.closed_at = timezone.now()
            ticket.save()
            messages.success(request, 'Ticket closed.')
        
        elif action == 'assign':
            ticket.assigned_to = request.user
            ticket.save()
            messages.success(request, 'Ticket assigned to you.')
        
        elif action == 'change_priority':
            ticket.priority = request.POST.get('priority', ticket.priority)
            ticket.save()
            messages.success(request, 'Priority updated.')
        
        return redirect('admin_ticket_detail', ticket_id=ticket.id)
    
    context = {
        'ticket': ticket,
        'messages': ticket_messages,
    }
    
    return render(request, 'admin_panel/tickets/detail.html', context)


# =============================================================================
# ANNOUNCEMENT MANAGEMENT
# =============================================================================

@admin_required
def announcement_list(request):
    """
    List all announcements.
    """
    announcements = Announcement.objects.order_by('-created_at')
    
    context = {
        'announcements': announcements,
    }
    
    return render(request, 'admin_panel/announcements/list.html', context)


@admin_required
@require_http_methods(["GET", "POST"])
def announcement_edit(request, announcement_id=0):
    """
    Create or edit an announcement.
    """
    if announcement_id:
        announcement = get_object_or_404(Announcement, id=announcement_id)
    else:
        announcement = None
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        message = request.POST.get('message', '').strip()
        announcement_type = request.POST.get('announcement_type', 'info')
        target_audience = request.POST.get('target_audience', 'all')
        is_active = request.POST.get('is_active') == 'on'
        is_dismissible = request.POST.get('is_dismissible') == 'on'
        is_banner = request.POST.get('is_banner') == 'on'
        link_url = request.POST.get('link_url', '').strip()
        link_text = request.POST.get('link_text', 'Learn More').strip()
        
        # Parse datetime fields - treat input as IST (Asia/Kolkata)
        from datetime import datetime
        import pytz
        ist = pytz.timezone('Asia/Kolkata')
        
        starts_at_str = request.POST.get('starts_at', '').strip()
        ends_at_str = request.POST.get('ends_at', '').strip()
        
        if starts_at_str:
            # Parse the datetime-local format and localize to IST
            naive_dt = datetime.strptime(starts_at_str, '%Y-%m-%dT%H:%M')
            starts_at = ist.localize(naive_dt)
        else:
            starts_at = timezone.now()
        
        if ends_at_str:
            naive_dt = datetime.strptime(ends_at_str, '%Y-%m-%dT%H:%M')
            ends_at = ist.localize(naive_dt)
        else:
            ends_at = None
        
        if announcement:
            announcement.title = title
            announcement.message = message
            announcement.announcement_type = announcement_type
            announcement.target_audience = target_audience
            announcement.is_active = is_active
            announcement.is_dismissible = is_dismissible
            announcement.is_banner = is_banner
            announcement.link_url = link_url
            announcement.link_text = link_text
            announcement.starts_at = starts_at
            announcement.ends_at = ends_at
            announcement.save()
            messages.success(request, 'Announcement updated.')
        else:
            Announcement.objects.create(
                title=title,
                message=message,
                announcement_type=announcement_type,
                target_audience=target_audience,
                is_active=is_active,
                is_dismissible=is_dismissible,
                is_banner=is_banner,
                link_url=link_url,
                link_text=link_text,
                starts_at=starts_at,
                ends_at=ends_at,
                created_by=request.user,
            )
            messages.success(request, 'Announcement created.')
        
        return redirect('admin_announcement_list')
    
    context = {
        'announcement': announcement,
    }
    
    return render(request, 'admin_panel/announcements/edit.html', context)


@admin_required
@require_POST
def announcement_delete(request, announcement_id):
    """
    Delete an announcement.
    """
    announcement = get_object_or_404(Announcement, id=announcement_id)
    announcement.delete()
    messages.success(request, 'Announcement deleted.')
    
    return redirect('admin_announcement_list')


# =============================================================================
# FAQ MANAGEMENT
# =============================================================================

@admin_required
def faq_list(request):
    """
    List all FAQ categories and items.
    """
    categories = FAQCategory.objects.prefetch_related('faq_items').order_by('display_order')
    
    context = {
        'categories': categories,
    }
    
    return render(request, 'admin_panel/faq/list.html', context)


@admin_required
@require_http_methods(["GET", "POST"])
def faq_category_edit(request, category_id=0):
    """
    Create or edit FAQ category.
    """
    if category_id:
        category = get_object_or_404(FAQCategory, id=category_id)
    else:
        category = None
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        slug = request.POST.get('slug', '').strip().lower()
        icon = request.POST.get('icon', '').strip()
        display_order = int(request.POST.get('display_order', 0))
        is_active = request.POST.get('is_active') == 'on'
        
        if category:
            category.name = name
            category.slug = slug
            category.icon = icon
            category.display_order = display_order
            category.is_active = is_active
            category.save()
            messages.success(request, 'Category updated.')
        else:
            FAQCategory.objects.create(
                name=name,
                slug=slug,
                icon=icon,
                display_order=display_order,
                is_active=is_active,
            )
            messages.success(request, 'Category created.')
        
        return redirect('admin_faq_list')
    
    context = {
        'category': category,
    }
    
    return render(request, 'admin_panel/faq/category_edit.html', context)


@admin_required
@require_http_methods(["GET", "POST"])
def faq_item_edit(request, item_id=0):
    """
    Create or edit FAQ item.
    """
    categories = FAQCategory.objects.all().order_by('display_order')
    
    if item_id:
        item = get_object_or_404(FAQItem, id=item_id)
        category = item.category
    else:
        item = None
        # Check for category from query param
        cat_id = request.GET.get('category') or request.POST.get('category')
        category = FAQCategory.objects.filter(id=cat_id).first() if cat_id else None
    
    if request.method == 'POST':
        question = request.POST.get('question', '').strip()
        answer = request.POST.get('answer', '').strip()
        display_order = int(request.POST.get('display_order', 0))
        is_active = request.POST.get('is_active') == 'on'
        is_featured = request.POST.get('is_featured') == 'on'
        category_id = request.POST.get('category')
        
        if not category and category_id:
            category = get_object_or_404(FAQCategory, id=category_id)
        
        if item:
            item.question = question
            item.answer = answer
            item.display_order = display_order
            item.is_active = is_active
            item.is_featured = is_featured
            if category:
                item.category = category
            item.save()
            messages.success(request, 'FAQ updated.')
        else:
            if not category:
                messages.error(request, 'Please select a category.')
                return redirect('admin_faq_list')
            FAQItem.objects.create(
                category=category,
                question=question,
                answer=answer,
                display_order=display_order,
                is_active=is_active,
                is_featured=is_featured,
            )
            messages.success(request, 'FAQ created.')
        
        return redirect('admin_faq_list')
    
    context = {
        'categories': categories,
        'category': category,
        'item': item,
        'selected_category': int(request.GET.get('category', 0)) if request.GET.get('category') else None,
    }
    
    return render(request, 'admin_panel/faq/item_edit.html', context)


@admin_required
@require_POST
def faq_item_delete(request, item_id):
    """
    Delete an FAQ item.
    """
    item = get_object_or_404(FAQItem, id=item_id)
    item.delete()
    messages.success(request, 'FAQ deleted.')
    return redirect('admin_faq_list')


# =============================================================================
# PAYMENT MANAGEMENT
# =============================================================================

@admin_required
def payment_list(request):
    """
    List all payments.
    """
    payments = Payment.objects.select_related('user').order_by('-created_at')
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        payments = payments.filter(status=status)
    
    # Search
    search = request.GET.get('q', '').strip()
    if search:
        payments = payments.filter(
            Q(user__username__icontains=search) |
            Q(order_id__icontains=search) |
            Q(payment_id__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(payments, 25)
    page = request.GET.get('page', 1)
    payments_page = paginator.get_page(page)
    
    context = {
        'payments': payments_page,
        'status': status,
        'search': search,
    }
    
    return render(request, 'admin_panel/payments/list.html', context)


@admin_required
def payment_detail(request, payment_id):
    """
    View payment details.
    """
    payment = get_object_or_404(Payment, id=payment_id)
    
    context = {
        'payment': payment,
    }
    
    return render(request, 'admin_panel/payments/detail.html', context)
