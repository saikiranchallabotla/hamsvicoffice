# core/auth_views.py
"""
Authentication views for user registration, login, logout, and profile management
Now with organization scoping and multi-tenant support.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.db import IntegrityError

from .models import UserProfile, Organization, Membership, Estimate, Project
from .decorators import org_required


def register(request):
    """User registration view - automatically creates organization on signup"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        company_name = request.POST.get('company_name', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        # Validation
        errors = []
        
        if not username:
            errors.append("Username is required.")
        elif len(username) < 3:
            errors.append("Username must be at least 3 characters.")
        elif User.objects.filter(username=username).exists():
            errors.append("Username already exists.")
        
        if not email:
            errors.append("Email is required.")
        elif User.objects.filter(email=email).exists():
            errors.append("Email already registered.")
        
        if not password:
            errors.append("Password is required.")
        elif len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        
        if password != confirm_password:
            errors.append("Passwords do not match.")
        
        if errors:
            return render(request, 'core/register.html', {
                'errors': errors,
                'username': username,
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'company_name': company_name,
            })
        
        # Create user (signals will auto-create Organization + Membership)
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
            
            # Update profile with company name (profile auto-created by signals)
            # Use get_or_create in case signal hasn't fired yet
            from core.models import UserProfile
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.company_name = company_name
            profile.subscription_tier = 'free'
            profile.save()
            
            messages.success(request, 'Registration successful! Please log in.')
            return redirect('login')
            
        except IntegrityError as e:
            messages.error(request, 'An error occurred during registration. Please try again.')
            return render(request, 'core/register.html', {
                'username': username,
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'company_name': company_name,
            })
    
    return render(request, 'core/register.html')


def login_view(request):
    """User login view"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
            return render(request, 'core/login.html', {'username': username})
    
    return render(request, 'core/login.html')


@login_required(login_url='login')
def logout_view(request):
    """User logout view"""
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login')


@org_required
def dashboard(request):
    """User dashboard showing recent estimates and projects - organization scoped"""
    user = request.user
    org = request.organization
    profile = user.userprofile if hasattr(user, 'userprofile') else None
    
    # Get org's recent estimates and projects
    recent_estimates = Estimate.objects.for_org(org)[:10]
    projects = Project.objects.for_org(org)
    members = Membership.objects.filter(organization=org).count()
    
    context = {
        'organization': org,
        'profile': profile,
        'recent_estimates': recent_estimates,
        'projects': projects,
        'total_estimates': Estimate.objects.for_org(org).count(),
        'total_projects': projects.count(),
        'total_members': members,
        'user_role': Membership.objects.get(user=user, organization=org).get_role_display(),
    }
    
    return render(request, 'core/dashboard.html', context)


@org_required
def profile_view(request):
    """User profile view - organization scoped"""
    user = request.user
    org = request.organization
    profile = user.userprofile if hasattr(user, 'userprofile') else None
    membership = Membership.objects.get(user=user, organization=org)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_profile':
            user.first_name = request.POST.get('first_name', user.first_name)
            user.last_name = request.POST.get('last_name', user.last_name)
            user.email = request.POST.get('email', user.email)
            user.save()
            
            if profile:
                profile.company_name = request.POST.get('company_name', profile.company_name)
                profile.save()
            
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
        
        elif action == 'change_password':
            from django.contrib.auth import update_session_auth_hash
            from django.contrib.auth.hashers import check_password
            
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')
            
            if not check_password(current_password, user.password):
                messages.error(request, 'Current password is incorrect.')
            elif len(new_password) < 8:
                messages.error(request, 'New password must be at least 8 characters.')
            elif new_password != confirm_password:
                messages.error(request, 'New passwords do not match.')
            else:
                user.set_password(new_password)
                user.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Password changed successfully!')
                return redirect('profile')
    
    context = {
        'organization': org,
        'profile': profile,
        'user': user,
        'membership': membership,
    }
    
    return render(request, 'core/profile.html', context)


@org_required
def my_estimates(request):
    """List organization's estimates - organization scoped"""
    org = request.organization
    status_filter = request.GET.get('status', 'all')
    
    estimates = Estimate.objects.for_org(org)
    
    if status_filter != 'all':
        estimates = estimates.filter(status=status_filter)
    
    context = {
        'organization': org,
        'estimates': estimates,
        'status_filter': status_filter,
        'status_choices': Estimate._meta.get_field('status').choices,
    }
    
    return render(request, 'core/my_estimates.html', context)


@org_required
def view_estimate(request, estimate_id):
    """View a specific estimate - organization scoped"""
    org = request.organization
    estimate = get_object_or_404(Estimate, id=estimate_id, organization=org)
    
    context = {
        'organization': org,
        'estimate': estimate,
        'estimate_data': estimate.estimate_data,
    }
    
    return render(request, 'core/view_estimate.html', context)


@org_required
def delete_estimate(request, estimate_id):
    """Delete an estimate (soft delete via status change) - organization scoped"""
    org = request.organization
    estimate = get_object_or_404(Estimate, id=estimate_id, organization=org)
    
    if request.method == 'POST':
        estimate.status = 'archived'
        estimate.save()
        messages.success(request, 'Estimate archived successfully.')
        return redirect('my_estimates')
    
    return render(request, 'core/confirm_delete.html', {'estimate': estimate})


@org_required
@require_POST
def save_estimate(request):
    """Save current workslip as an estimate - organization scoped"""
    org = request.organization
    user = request.user
    
    work_name = request.POST.get('work_name', 'Untitled Estimate')
    project_id = request.POST.get('project_id')
    category = request.POST.get('category', 'electrical')
    total_amount = request.POST.get('total_amount', 0)
    
    # Check user limit (free tier)
    profile = user.userprofile if hasattr(user, 'userprofile') else None
    if profile and not profile.can_create_estimate():
        return JsonResponse({
            'success': False,
            'error': f'You have reached your estimate limit ({profile.estimates_limit}). Upgrade to Pro for unlimited estimates.'
        })
    
    # Get estimate data from session
    estimate_data = {
        'ws_estimate_rows': request.session.get('ws_estimate_rows', []),
        'ws_exec_map': request.session.get('ws_exec_map', {}),
        'ws_tp_percent': request.session.get('ws_tp_percent', 0),
        'ws_tp_type': request.session.get('ws_tp_type', 'Excess'),
        'ws_supp_items': request.session.get('ws_supp_items', []),
    }
    
    project = None
    if project_id:
        # Verify project belongs to organization
        project = get_object_or_404(Project, id=project_id, organization=org)
    
    estimate = Estimate.objects.create(
        user=user,
        organization=org,
        project=project,
        work_name=work_name,
        category=category,
        estimate_data=estimate_data,
        total_amount=total_amount,
        status='draft'
    )
    
    # Increment user's estimate count for free tier tracking
    if profile:
        profile.estimates_created += 1
        profile.save()
    
    return JsonResponse({
        'success': True,
        'estimate_id': estimate.id,
        'message': f'Estimate "{work_name}" saved successfully!'
    })

