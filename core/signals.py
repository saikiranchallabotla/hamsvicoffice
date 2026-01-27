# core/signals.py
"""
Django signals for automatic organization and membership creation.
Triggered when new users are created.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from core.models import Organization, Membership, UserProfile


logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Create UserProfile when new User is created.
    Also creates a default Organization for the user.
    """
    if not created:
        return
    
    try:
        # Create UserProfile
        UserProfile.objects.get_or_create(user=instance)
        
        # Create default Organization for the user
        org_slug = instance.username.lower().replace(' ', '-')
        org_name = f"{instance.first_name or instance.username}'s Organization"
        
        organization = Organization.objects.create(
            name=org_name,
            slug=org_slug,
            plan=Organization.PlanType.FREE,
            owner=instance,
        )
        
        # Create owner membership
        Membership.objects.create(
            user=instance,
            organization=organization,
            role=Membership.MembershipRole.OWNER,
        )
        
        logger.info(
            f"Auto-created organization '{organization.name}' "
            f"and membership for user {instance.username}"
        )
    
    except Exception as e:
        logger.error(f"Error creating organization for user {instance.username}: {e}")


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, created, **kwargs):
    """
    Save UserProfile when User is saved.
    """
    if created:
        return  # Already handled in create_user_profile
    
    try:
        # Check if profile exists via the model, not via relation
        profile = UserProfile.objects.filter(user=instance).first()
        if profile:
            profile.save()
    except Exception as e:
        logger.error(f"Error saving UserProfile for {instance.username}: {e}")
