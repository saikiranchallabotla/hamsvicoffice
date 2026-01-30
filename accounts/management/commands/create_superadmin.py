# accounts/management/commands/create_superadmin.py
"""
Management command to create or promote a user to superadmin.
This is used during initial deployment to set up the first admin.

Usage:
    python manage.py create_superadmin --email your@email.com --password yourpassword
    python manage.py create_superadmin --username existing_user --promote
"""

import getpass
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from accounts.models import UserProfile


class Command(BaseCommand):
    help = 'Create a new superadmin user or promote an existing user to superadmin'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Email address for the new superadmin'
        )
        parser.add_argument(
            '--username',
            type=str,
            help='Username for the new superadmin or existing user to promote'
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Password (will prompt if not provided for new users)'
        )
        parser.add_argument(
            '--promote',
            action='store_true',
            help='Promote an existing user to superadmin'
        )
        parser.add_argument(
            '--first-name',
            type=str,
            default='',
            help='First name for the new user'
        )
        parser.add_argument(
            '--last-name',
            type=str,
            default='',
            help='Last name for the new user'
        )

    def handle(self, *args, **options):
        email = options.get('email')
        username = options.get('username')
        password = options.get('password')
        promote = options.get('promote')
        first_name = options.get('first_name') or ''
        last_name = options.get('last_name') or ''

        if promote:
            # Promote existing user
            if not username and not email:
                raise CommandError('Please provide --username or --email to identify the user to promote')
            
            if username:
                user = User.objects.filter(username=username).first()
            else:
                user = User.objects.filter(email=email).first()
            
            if not user:
                raise CommandError(f'User not found')
            
            # Get or create profile
            profile, created = UserProfile.objects.get_or_create(user=user)
            old_role = profile.role
            profile.role = 'superadmin'
            profile.save()
            
            # Also make Django superuser
            user.is_staff = True
            user.is_superuser = True
            user.save()
            
            self.stdout.write(self.style.SUCCESS(
                f'Successfully promoted "{user.username}" from {old_role} to superadmin'
            ))
            
        else:
            # Create new superadmin
            if not email:
                raise CommandError('Please provide --email for the new superadmin')
            
            # Check if user exists
            if User.objects.filter(email=email).exists():
                raise CommandError(f'User with email {email} already exists. Use --promote to upgrade them.')
            
            # Generate username from email if not provided
            if not username:
                username = email.split('@')[0]
                # Ensure unique username
                base_username = username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
            
            # Get password
            if not password:
                password = getpass.getpass('Enter password for superadmin: ')
                password_confirm = getpass.getpass('Confirm password: ')
                if password != password_confirm:
                    raise CommandError('Passwords do not match')
            
            if len(password) < 8:
                raise CommandError('Password must be at least 8 characters')
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_staff=True,
                is_superuser=True
            )
            
            # Create profile with superadmin role
            UserProfile.objects.create(
                user=user,
                role='superadmin',
                email_verified=True,
                profile_completed=True
            )
            
            self.stdout.write(self.style.SUCCESS(
                f'Successfully created superadmin:\n'
                f'  Username: {username}\n'
                f'  Email: {email}\n'
                f'  Role: superadmin'
            ))
            self.stdout.write(self.style.WARNING(
                'Please change the password after first login!'
            ))
