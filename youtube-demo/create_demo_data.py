"""
Create realistic demo data for HAMSVIC Office product video.
Sets up subscriptions, saved works, and letter settings for a polished demo.
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'estimate_site.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import UserProfile
from subscriptions.models import Module, UserModuleSubscription, ModulePricing
from core.models import LetterSettings
from datetime import timedelta
from django.utils import timezone

User = get_user_model()


def setup_demo_user():
    user = User.objects.get(username='admin')
    user.first_name = 'Rajesh'
    user.last_name = 'Kumar'
    user.save()

    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.phone = '+919876543210'
    profile.phone_verified = True
    profile.save()

    print(f'Demo user: {user.first_name} {user.last_name} ({user.email})')
    return user


def grant_all_subscriptions(user):
    modules = Module.objects.filter(is_active=True)
    for module in modules:
        pricing = ModulePricing.objects.filter(module=module, duration_months=12).first()
        UserModuleSubscription.objects.update_or_create(
            user=user,
            module=module,
            defaults={
                'status': 'active',
                'started_at': timezone.now() - timedelta(days=30),
                'expires_at': timezone.now() + timedelta(days=335),
                'pricing': pricing,
            }
        )
    print(f'Granted {modules.count()} module subscriptions')


def setup_letter_settings(user):
    LetterSettings.objects.update_or_create(
        user=user,
        defaults={
            'government_name': 'Government of Telangana',
            'department_name': 'Energy Department',
            'officer_name': 'Rajesh Kumar',
            'officer_qualification': 'B.E. (Electrical)',
            'officer_designation': 'Assistant Engineer',
            'sub_division': 'Electrical Sub Division, Secunderabad',
            'office_address': 'O/o The AE, Electrical Sub Division, Secunderabad - 500003',
            'recipient_designation': 'Executive Engineer',
            'recipient_division': 'Electrical Division, Hyderabad',
            'recipient_address': 'O/o The EE, Electrical Division, Hyderabad - 500001',
            'office_code': 'AE/ESD/SEC',
            'superior_designation': 'Superintending Engineer',
        }
    )
    print('Letter settings configured')


def main():
    print('=== Creating Demo Data ===')
    user = setup_demo_user()
    grant_all_subscriptions(user)
    setup_letter_settings(user)
    print('=== Demo data ready ===')


if __name__ == '__main__':
    main()
