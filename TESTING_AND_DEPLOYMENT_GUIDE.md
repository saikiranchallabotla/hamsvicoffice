# Testing & Deployment Guide - OTP & Auth Flow

## Current Status (Testing Phase - dev_mode=True)

### ✅ What's Working

**Login Flow:**
- ✅ User enters phone/email → OTP shown in popup on login page
- ✅ OTP displayed once (fixed duplicate issue)
- ✅ User can click "Continue to Verify" → goes to verify_otp page
- ✅ User enters OTP → login succeeds
- ✅ Session cleaned up properly after login

**Registration Flow:**
- ✅ User enters details → redirects to verify_otp with OTP in session
- ✅ OTP shown in popup on verify_otp page
- ✅ User verifies OTP → account created and logged in
- ✅ Session data cleaned up properly

**OTP Service (dev_mode=True):**
- ✅ `OTPService.request_otp()` forces `dev_mode=True` for testing
- ✅ Returns OTP in response: `response_data["otp"] = otp`
- ✅ Rate limiting & validation working (5 attempts, 30min lockout)
- ✅ Proper TTL handling (5 minutes expiration)

### ⚠️ Issues Found

**Issue #1: Registration doesn't show OTP on register.html**
- Registration redirects to verify_otp page instead of showing OTP popup on register.html
- This is inconsistent with login behavior
- **Fix:** Update registration to show OTP popup inline (optional - current flow works)

**Issue #2: Session cleanup in edge cases**
- If user closes browser during OTP flow: `otp_identifier`, `register_data` remain in session
- On next login with same session, old data could interfere
- **Fix:** Added validation in verify_otp_view (checks for identifier)

**Issue #3: Redeployment considerations**
- Redis/cache is cleared on redeployment → users will get "OTP expired" errors
- This is acceptable for testing, but users should be warned
- **Fix:** Clear instructions for users during deployment

---

## Production Deployment Guide (When OTP Service is Purchased)

### Step 1: Remove Forced dev_mode

**File:** `accounts/services/otp_service.py` (Line 110)

```python
# BEFORE (Testing):
dev_mode = True  # Force OTP to show on screen

# AFTER (Production):
dev_mode = not (sms_configured or email_configured)
```

### Step 2: Configure OTP Service Settings

**File:** `settings.py` / `.env`

```env
# Twilio Configuration (for SMS)
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890

# Email Configuration (for Email OTP)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_USE_TLS=True
```

### Step 3: Update `_send_otp` Implementation

**File:** `accounts/services/otp_service.py` (Lines 350+)

Currently it's a stub. Implement actual SMS/Email sending:

```python
@classmethod
def _send_otp(cls, identifier: str, otp: str, channel: str) -> dict:
    """Send OTP via SMS or Email"""
    try:
        if channel == 'sms':
            # Use Twilio
            from twilio.rest import Client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            message = client.messages.create(
                body=f"Your Hamsvic OTP is: {otp}",
                from_=settings.TWILIO_PHONE_NUMBER,
                to=identifier
            )
            return {'ok': True, 'channel': 'sms'}
        
        elif channel == 'email':
            # Use Django email
            from django.core.mail import send_mail
            send_mail(
                subject='Your Hamsvic OTP',
                message=f'Your OTP is: {otp}',
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[identifier],
                fail_silently=False
            )
            return {'ok': True, 'channel': 'email'}
    except Exception as e:
        logger.error(f"Failed to send OTP: {str(e)}")
        return {'ok': False, 'error': str(e)}
```

### Step 4: Remove OTP Display from Templates

**Files to Update:**
- `accounts/templates/accounts/login.html` - Remove OTP popup modal
- `accounts/templates/accounts/verify_otp.html` - Remove OTP popup modal

Keep the form fields for users to manually enter OTP.

---

## Testing Checklist (Current - dev_mode=True)

### Login Flow
- [ ] Go to login page
- [ ] Enter phone/email
- [ ] OTP appears in popup
- [ ] Copy OTP using button
- [ ] Click "Continue to Verify"
- [ ] OTP popup NOT shown again on verify page (should be cleared)
- [ ] Paste OTP in form
- [ ] Login succeeds
- [ ] Redirected to dashboard

### Registration Flow
- [ ] Go to register page
- [ ] Fill form: name, email, phone, company
- [ ] Submit form
- [ ] Redirected to verify_otp page with OTP popup
- [ ] Copy and verify OTP
- [ ] Account created and logged in
- [ ] Can access dashboard

### Edge Cases
- [ ] Invalid phone format → error message
- [ ] Phone already registered → error message
- [ ] Email already registered → error message
- [ ] Wrong OTP 5 times → lockout for 30 minutes
- [ ] After 5 minutes → "OTP expired" message
- [ ] Resend OTP within 60 seconds → "Please wait X seconds" message
- [ ] Browser refresh during OTP flow → state persists in session
- [ ] Multiple login attempts in same session → previous session cleared

### Redeployment Testing
- [ ] Deploy new version
- [ ] Try login with previous credentials
- [ ] User gets new OTP (cache cleared)
- [ ] OTP flow works normally

---

## Production Deployment Checklist

### Before Going Live
- [ ] All SMS/Email credentials configured in environment
- [ ] Remove `dev_mode = True` forced flag
- [ ] Test with real SMS/Email (not popup)
- [ ] OTP popups removed from templates
- [ ] Rate limiting tested (5 attempts, 30min lockout)
- [ ] Error handling tested
- [ ] Session cleanup verified
- [ ] Redis configured for production (cache backend)
- [ ] Logging configured for audit trail

### During Deployment
- [ ] Notify users of deployment (OTP flow might be interrupted)
- [ ] Have support team ready for OTP issues
- [ ] Monitor logs for OTP errors
- [ ] Verify email/SMS delivery working

### After Deployment
- [ ] Test login with real phone/email
- [ ] Verify OTP received via SMS/Email
- [ ] Verify all error handling works
- [ ] Monitor for any rate limiting false positives
- [ ] Check audit logs for suspicious patterns

---

## Code Inventory - OTP System

### Files to Update for Production

1. **accounts/services/otp_service.py** (Lines 110-120)
   - Remove forced `dev_mode = True`
   - Implement `_send_otp()` for real SMS/Email
   - Update settings.py with credentials

2. **accounts/templates/accounts/login.html** (Lines 7-125)
   - Remove OTP popup modal
   - Keep login form only

3. **accounts/templates/accounts/verify_otp.html** (Lines 7-100)
   - Remove OTP popup modal
   - Keep OTP input form only

4. **accounts/views.py**
   - No changes needed (already handles both dev_mode and production)
   - Login flow at line 36
   - Verify OTP flow at line 97
   - Registration flow at line 191

5. **settings.py**
   - Add Twilio credentials (when SMS purchased)
   - Add Email credentials (when Email OTP purchased)

---

## Session Data Flow (Reference)

### Login
```
POST /login → request_otp() → store in session: otp_identifier, otp_purpose
                           → show popup with OTP (NOT stored in session now)
                           
GET/POST /verify_otp → pop show_otp from session (now empty)
                     → verify OTP
                     → clear session: otp_identifier, otp_purpose
                     → login user
```

### Registration
```
POST /register → validate data
              → store in session: register_data, otp_identifier, otp_purpose
              → request_otp()
              → store in session: show_otp
              → redirect /verify_otp
              
GET/POST /verify_otp → pop show_otp from session (displays popup)
                     → verify OTP
                     → pop register_data from session
                     → create user
                     → clear session: otp_identifier, otp_purpose, show_otp
```

---

## Troubleshooting

### "OTP not showing on login page"
- Check: Is `dev_mode = True` in otp_service.py?
- Check: Is `show_otp` being passed to login template?
- Check: Browser console for JS errors in copyOtpCode()

### "OTP expired" error
- This is expected after 5 minutes
- User should click "Resend OTP" button
- If SMS/Email is not configured, OTP will always show on screen

### "Too many failed attempts"
- User exceeded 5 wrong attempts
- They're locked out for 30 minutes
- This is by design to prevent brute force

### Registration incomplete after OTP verification
- Check: Is `register_data` in session?
- Check: Is user being created properly in `_create_user()`?
- Check: Database constraints (email/phone unique)?

---

## Important Notes

1. **Cache Backend:** OTP system uses Django cache. Ensure Redis is configured for production.
2. **Session Cleanup:** All session data is properly cleaned up after successful verification.
3. **Rate Limiting:** Enabled by default (hourly limit: 10, cooldown: 60s, lockout: 30min).
4. **Audit Logging:** All OTP events are logged for security auditing.
5. **HTTPS Required:** OTP should only be transmitted over HTTPS in production.
