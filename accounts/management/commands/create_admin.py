"""
Management command to create admin user from environment variables.
Run: python manage.py create_admin
"""
import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import UserProfile

User = get_user_model()


class Command(BaseCommand):
    help = 'Create admin superuser from environment variables'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Admin email (or set ADMIN_EMAIL env var)')
        parser.add_argument('--password', type=str, help='Admin password (or set ADMIN_PASSWORD env var)')
        parser.add_argument('--phone', type=str, help='Admin phone (or set ADMIN_PHONE env var)')

    def handle(self, *args, **options):
        email = options.get('email') or os.environ.get('ADMIN_EMAIL', '')
        password = options.get('password') or os.environ.get('ADMIN_PASSWORD', '')
        phone = options.get('phone') or os.environ.get('ADMIN_PHONE', '')
        first_name = os.environ.get('ADMIN_FIRST_NAME', 'Admin')
        last_name = os.environ.get('ADMIN_LAST_NAME', '')

        if not email or not password:
            self.stdout.write(self.style.ERROR(
                'ADMIN_EMAIL and ADMIN_PASSWORD are required.\n'
                'Set them as environment variables or pass --email and --password flags.'
            ))
            return

        user = None

        # Check if user exists by email
        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
            self.stdout.write(f'Found user by email: {email}')

        # Check if user exists by phone in profile
        if not user and phone:
            phone_variants = [phone]
            if phone.startswith('+'):
                phone_variants.append(phone.lstrip('+').lstrip('0'))
            profile = UserProfile.objects.filter(phone__in=phone_variants).first()
            if profile:
                user = profile.user
                self.stdout.write(f'Found user by phone: {profile.phone}')

        if user:
            # Update existing user to superuser
            user.is_staff = True
            user.is_superuser = True
            if not user.email:
                user.email = email
            user.save()
            self.stdout.write(self.style.SUCCESS(f'User {user.username} updated to superuser!'))
        else:
            # Create new superuser
            user = User.objects.create_superuser(
                username='admin',
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
            self.stdout.write(self.style.SUCCESS(f'Superuser created: {email}'))

        # Create or update UserProfile with phone
        profile, created = UserProfile.objects.get_or_create(user=user)
        if phone:
            profile.phone = phone
            profile.phone_verified = True
            profile.save()

        self.stdout.write(self.style.SUCCESS(f'Admin ready: {email}'))
        self.stdout.write(self.style.WARNING('Please change the default password after first login!'))
