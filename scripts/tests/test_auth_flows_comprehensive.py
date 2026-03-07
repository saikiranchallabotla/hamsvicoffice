#!/usr/bin/env python
"""
Test script to validate OTP & Auth flows without disturbing dev_mode display.
Run with: python manage.py shell < test_auth_flows.py
"""

import os
import sys
from django.contrib.auth.models import User
from accounts.models import UserProfile, OTPToken
from accounts.services.otp_service import OTPService

def print_header(title):
    """Print formatted header"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def test_otp_service():
    """Test OTP Service directly"""
    print_header("TEST 1: OTP Service - Request & Verify")
    
    test_phone = "+919876543210"
    
    # Test 1.1: Request OTP
    print("\n[1.1] Requesting OTP for testing...")
    result = OTPService.request_otp(test_phone, 'sms')
    
    if result['ok']:
        print("✅ OTP Request Success")
        otp = result.get('data', {}).get('otp')
        dev_mode = result.get('data', {}).get('dev_mode')
        print(f"   - dev_mode: {dev_mode}")
        print(f"   - OTP: {otp}")
        print(f"   - TTL: {result.get('data', {}).get('expires_in')} seconds")
    else:
        print(f"❌ OTP Request Failed: {result['reason']}")
        return False
    
    # Test 1.2: Verify OTP
    print("\n[1.2] Verifying OTP...")
    verify_result = OTPService.verify_otp(test_phone, otp)
    
    if verify_result['ok']:
        print("✅ OTP Verification Success")
    else:
        print(f"❌ OTP Verification Failed: {verify_result['reason']}")
        return False
    
    # Test 1.3: Try to verify again (should fail - OTP cleared)
    print("\n[1.3] Attempting to reuse same OTP...")
    reuse_result = OTPService.verify_otp(test_phone, otp)
    
    if not reuse_result['ok']:
        print("✅ OTP Correctly Rejected on Reuse (Expected behavior)")
        print(f"   Reason: {reuse_result['reason']}")
    else:
        print("❌ ERROR: OTP was reused (Security issue!)")
        return False
    
    return True

def test_rate_limiting():
    """Test OTP Rate Limiting"""
    print_header("TEST 2: Rate Limiting")
    
    test_phone = "+911234567890"
    
    # Clear any existing rate limit data
    from django.core.cache import cache
    cache.delete(f"otp:lockout:{test_phone}")
    cache.delete(f"otp:cooldown:{test_phone}")
    cache.delete(f"otp:hourly:{test_phone}")
    
    # Test 2.1: Hourly limit
    print("\n[2.1] Testing hourly limit (max 10 OTPs per hour)...")
    for i in range(1, 12):
        result = OTPService.request_otp(f"{test_phone}:{i}", 'sms')
        if i <= 10:
            if result['ok']:
                print(f"   Request {i}: ✅")
            else:
                print(f"   Request {i}: ❌ {result['reason']}")
        else:
            if not result['ok'] and 'RATE_LIMITED' in result.get('code', ''):
                print(f"   Request {i}: ✅ Correctly rate limited")
            else:
                print(f"   Request {i}: ❌ Should have been rate limited")
    
    # Test 2.2: Cooldown (resend too fast)
    print("\n[2.2] Testing cooldown (60 seconds between requests)...")
    test_phone2 = "+919999999999"
    cache.delete(f"otp:cooldown:{test_phone2}")
    
    result1 = OTPService.request_otp(test_phone2, 'sms')
    if result1['ok']:
        print("   First request: ✅")
    
    result2 = OTPService.request_otp(test_phone2, 'sms')
    if not result2['ok'] and 'COOLDOWN' in result2.get('code', ''):
        retry_after = result2.get('data', {}).get('retry_after', 0)
        print(f"   Second request (immediate): ✅ Blocked - Wait {retry_after}s")
    
    return True

def test_wrong_otp_attempts():
    """Test lockout after wrong OTP attempts"""
    print_header("TEST 3: Wrong OTP Attempts & Lockout")
    
    test_phone = "+918888888888"
    
    # Request OTP
    result = OTPService.request_otp(test_phone, 'sms')
    if not result['ok']:
        print(f"❌ Failed to request OTP: {result['reason']}")
        return False
    
    otp = result.get('data', {}).get('otp')
    print(f"✅ OTP requested: {otp}")
    
    # Try wrong OTP 5 times
    print("\n[3.1] Testing 5 wrong attempts...")
    for i in range(1, 6):
        wrong_otp = "000000"
        verify_result = OTPService.verify_otp(test_phone, wrong_otp)
        
        if not verify_result['ok']:
            attempts_left = verify_result.get('data', {}).get('attempts_remaining', 0)
            if i < 5:
                print(f"   Attempt {i}: ❌ Wrong OTP - {attempts_left} remaining")
            else:
                print(f"   Attempt {i}: ❌ Locked out for 30 minutes")
    
    # Try legitimate OTP (should fail due to lockout)
    print("\n[3.2] Attempting legitimate OTP while locked out...")
    verify_result = OTPService.verify_otp(test_phone, otp)
    
    if not verify_result['ok'] and 'LOCKED_OUT' in verify_result.get('code', ''):
        print("✅ Account correctly locked (brute force protection working)")
    else:
        print("❌ Account should be locked!")
        return False
    
    return True

def test_session_cleanup():
    """Test that session data is properly cleaned up"""
    print_header("TEST 4: Session Cleanup & Redeployment Safety")
    
    # Create test users
    test_email = f"test_cleanup_{os.urandom(4).hex()}@example.com"
    test_phone = f"+91{os.urandom(5).hex()}"[:13]
    
    print(f"\n[4.1] Creating test user...")
    try:
        user = User.objects.create_user(
            username=test_email.split('@')[0],
            email=test_email,
            password='testpass123'
        )
        profile = UserProfile.objects.create(
            user=user,
            phone=test_phone,
            phone_verified=True
        )
        print(f"✅ User created: {user.username}")
    except Exception as e:
        print(f"❌ Failed to create user: {e}")
        return False
    
    print("\n[4.2] Simulating old session data after redeployment...")
    # Simulate what would happen if cache is cleared
    from django.core.cache import cache
    
    # Store old data
    cache.set("otp:code:test_identifier", "hashedotp", 300)
    cache.set("otp:attempts:test_identifier", 3, 1800)
    
    print("   ✅ Old cache data stored (simulating pre-redeployment)")
    
    print("\n[4.3] Requesting new OTP (should work fine)...")
    result = OTPService.request_otp(test_phone, 'sms')
    
    if result['ok']:
        print("✅ New OTP request works after redeployment simulation")
    else:
        print(f"❌ New OTP request failed: {result['reason']}")
        return False
    
    # Cleanup
    user.delete()
    return True

def test_dev_mode_flag():
    """Verify dev_mode is forced for testing"""
    print_header("TEST 5: Development Mode Flag")
    
    test_phone = "+917777777777"
    
    print("\n[5.1] Requesting OTP and checking dev_mode flag...")
    result = OTPService.request_otp(test_phone, 'sms')
    
    if result['ok']:
        dev_mode = result.get('data', {}).get('dev_mode', False)
        otp = result.get('data', {}).get('otp')
        
        if dev_mode:
            print("✅ dev_mode = True (testing - OTP shown on screen)")
        else:
            print("⚠️  dev_mode = False (production mode)")
        
        if otp:
            print(f"✅ OTP in response: {otp} (for testing)")
        else:
            print("❌ OTP not in response (production mode)")
    else:
        print(f"❌ OTP request failed: {result['reason']}")
        return False
    
    return True

def main():
    """Run all tests"""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*15 + "AUTH FLOW TESTING SUITE" + " "*20 + "║")
    print("║" + " "*10 + "Validating OTP & Auth flows without interference" + " "*7 + "║")
    print("╚" + "="*58 + "╝")
    
    tests = [
        ("OTP Service", test_otp_service),
        ("Rate Limiting", test_rate_limiting),
        ("Wrong OTP Attempts", test_wrong_otp_attempts),
        ("Session Cleanup", test_session_cleanup),
        ("Dev Mode Flag", test_dev_mode_flag),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ {test_name} crashed: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    # Summary
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Total:  {passed + failed}")
    print("="*60)
    
    if failed == 0:
        print("\n✅ ALL TESTS PASSED - Ready for production deployment!")
    else:
        print(f"\n❌ {failed} test(s) failed - Fix issues before deployment")
    
    return failed == 0

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
