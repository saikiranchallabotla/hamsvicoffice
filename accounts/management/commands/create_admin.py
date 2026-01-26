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
        username = 'admin'
        
        # Check if user already exists
        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f'User {email} updated to superuser!'))
        else:
            # Create new superuser
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password='Admin@123456',  # Temporary password
                first_name='Saikiran',
                last_name='Challabotla',
            )
            self.stdout.write(self.style.SUCCESS(f'Superuser created: {email}'))
        
        # Create or update UserProfile with phone
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.phone = phone
        profile.is_phone_verified = True
        profile.save()
        
        self.stdout.write(self.style.SUCCESS(f'Profile updated with phone: {phone}'))
        self.stdout.write(self.style.WARNING('='*50))
        self.stdout.write(self.style.WARNING('ADMIN CREDENTIALS:'))
        self.stdout.write(self.style.WARNING(f'Email: {email}'))
        self.stdout.write(self.style.WARNING(f'Phone: {phone}'))
        self.stdout.write(self.style.WARNING('Password: Admin@123456'))
        self.stdout.write(self.style.WARNING('='*50))
        self.stdout.write(self.style.WARNING('Please change this password after login!'))
