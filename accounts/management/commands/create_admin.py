"""
Management command to create admin user.
Run: python manage.py create_admin
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import UserProfile

User = get_user_model()


class Command(BaseCommand):
    help = 'Create admin superuser'

    def handle(self, *args, **options):
        email = 'saikiranchallabotla@gmail.com'
        phone = '+916304911990'
        phone_alt = '6304911990'  # Without country code
        username = 'admin'
        
        user = None
        
        # Check if user exists by email
        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
            self.stdout.write(f'Found user by email: {email}')
        
        # Check if user exists by phone in profile
        if not user:
            profile = UserProfile.objects.filter(phone__in=[phone, phone_alt]).first()
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
                username=username,
                email=email,
                password='Admin@123456',
                first_name='Saikiran',
                last_name='Challabotla',
            )
            self.stdout.write(self.style.SUCCESS(f'Superuser created: {email}'))
        
        # Create or update UserProfile with phone
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.phone = phone
        profile.phone_verified = True
        profile.save()
        
        self.stdout.write(self.style.SUCCESS(f'Profile updated with phone: {phone}'))
        self.stdout.write(self.style.WARNING('='*50))
        self.stdout.write(self.style.WARNING('ADMIN CREDENTIALS:'))
        self.stdout.write(self.style.WARNING(f'Username: {user.username}'))
        self.stdout.write(self.style.WARNING(f'Email: {email}'))
        self.stdout.write(self.style.WARNING(f'Phone: {phone}'))
        self.stdout.write(self.style.WARNING('='*50))
        self.stdout.write(self.style.WARNING('Please change this password after login!'))
