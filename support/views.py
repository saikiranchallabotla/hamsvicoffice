# support/views.py
"""
Support views for help center, FAQs, and tickets.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Q

from support.models import FAQCategory, FAQItem, HelpGuide, SupportTicket, TicketMessage


def help_center_view(request):
    """
    Public help center with FAQs and guides.
    """
    # Get FAQ categories with items
    categories = FAQCategory.objects.filter(is_active=True).prefetch_related(
        'faqs'
    ).order_by('display_order')
    
    # Get featured FAQs
    featured_faqs = FAQItem.objects.filter(
        is_published=True,
        is_featured=True
    ).select_related('category').order_by('display_order')[:6]
    
    # Get popular guides
    guides = HelpGuide.objects.filter(
        is_published=True
    ).order_by('-view_count')[:6]
    
    context = {
        'categories': categories,
        'featured_faqs': featured_faqs,
        'guides': guides,
    }
    
    return render(request, 'support/help_center.html', context)


def faq_category_view(request, category_slug):
    """
    View FAQs in a specific category.
    """
    category = get_object_or_404(FAQCategory, slug=category_slug, is_active=True)
    faqs = category.faqs.filter(is_published=True).order_by('display_order')
    
    context = {
        'category': category,
        'faqs': faqs,
    }
    
    return render(request, 'support/faq_category.html', context)


def guide_view(request, guide_slug):
    """
    View a help guide.
    """
    guide = get_object_or_404(HelpGuide, slug=guide_slug, is_published=True)
    
    # Increment view count atomically to prevent race conditions
    from django.db.models import F
    HelpGuide.objects.filter(id=guide.id).update(view_count=F('view_count') + 1)
    
    # Get related guides
    related = HelpGuide.objects.filter(
        is_published=True,
        module=guide.module
    ).exclude(id=guide.id)[:3]
    
    context = {
        'guide': guide,
        'related_guides': related,
    }
    
    return render(request, 'support/guide.html', context)


def search_help_view(request):
    """
    Search FAQs and guides.
    """
    query = request.GET.get('q', '').strip()
    
    if not query:
        return render(request, 'support/search_results.html', {'query': '', 'results': []})
    
    # Search FAQs
    faqs = FAQItem.objects.filter(
        is_published=True
    ).filter(
        Q(question__icontains=query) | Q(answer__icontains=query)
    )[:10]
    
    # Search guides
    guides = HelpGuide.objects.filter(
        is_published=True
    ).filter(
        Q(title__icontains=query) | Q(content__icontains=query)
    )[:10]
    
    context = {
        'query': query,
        'faqs': faqs,
        'guides': guides,
    }
    
    return render(request, 'support/search_results.html', context)


@login_required
def my_tickets_view(request):
    """
    User's support tickets.
    """
    tickets = SupportTicket.objects.filter(
        user=request.user
    ).order_by('-updated_at')
    
    context = {
        'tickets': tickets,
    }
    
    return render(request, 'support/my_tickets.html', context)


@login_required
def create_ticket_view(request):
    """
    Create a new support ticket.
    """
    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        category = request.POST.get('category', 'general')
        priority = request.POST.get('priority', 'medium')
        message = request.POST.get('message', '').strip()
        
        if not subject or not message:
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'support/create_ticket.html')
        
        # Create ticket
        ticket = SupportTicket.objects.create(
            user=request.user,
            subject=subject,
            category=category,
            priority=priority,
        )
        
        # Create first message
        TicketMessage.objects.create(
            ticket=ticket,
            sender=request.user,
            message=message,
        )
        
        messages.success(request, f'Ticket #{ticket.ticket_number} created successfully!')
        return redirect('view_ticket', ticket_id=ticket.id)
    
    return render(request, 'support/create_ticket.html')


@login_required
def view_ticket_view(request, ticket_id):
    """
    View a support ticket and its messages.
    """
    ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
    ticket_messages = ticket.messages.order_by('created_at')
    
    if request.method == 'POST':
        message = request.POST.get('message', '').strip()
        
        if message:
            TicketMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                message=message,
            )
            
            # Reopen if closed
            if ticket.status == 'closed':
                ticket.status = 'open'
                ticket.save()
            
            messages.success(request, 'Reply sent.')
            return redirect('view_ticket', ticket_id=ticket.id)
    
    context = {
        'ticket': ticket,
        'messages': ticket_messages,
    }
    
    return render(request, 'support/view_ticket.html', context)


@login_required
@require_POST
def close_ticket_view(request, ticket_id):
    """
    Close a support ticket.
    """
    ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
    
    ticket.status = 'closed'
    ticket.resolved_at = timezone.now()
    ticket.save()
    
    messages.success(request, f'Ticket #{ticket.ticket_number} closed.')
    return redirect('my_tickets')
