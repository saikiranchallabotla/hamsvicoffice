#!/usr/bin/env python
"""
Quick script to check if user data exists in PostgreSQL database
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'estimate_site.settings_railway')
django.setup()

from django.contrib.auth.models import User
from accounts.models import UserProfile

print("\n" + "="*60)
print("CHECKING USER DATA IN PostgreSQL DATABASE")
print("="*60)

# Check users
user_count = User.objects.count()
print(f"\n📊 Total Users in Database: {user_count}")

if user_count > 0:
    print("\n✅ USERS FOUND! Your data is NOT lost!\n")
    print("User Details:")
    print("-" * 60)
    
    for user in User.objects.all():
        try:
            profile = UserProfile.objects.get(user=user)
            company = profile.company_name if hasattr(profile, 'company_name') else 'N/A'
        except:
            company = 'N/A'
        
        print(f"  Username: {user.username}")
        print(f"  Email: {user.email}")
        print(f"  First Name: {user.first_name}")
        print(f"  Last Name: {user.last_name}")
        print(f"  Date Joined: {user.date_joined}")
        print(f"  Company: {company}")
        print("-" * 60)
else:
    print("\n❌ NO USERS FOUND in database")
    print("    This could mean:")
    print("    1. No users have registered yet")
    print("    2. Database was reset/migrated fresh")
    print("    3. Connection issue (but PostgreSQL is configured)")

print("\n" + "="*60)
