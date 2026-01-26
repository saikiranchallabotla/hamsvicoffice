# accounts/forms.py
"""
Account forms for profile management.
"""

from django import forms
from django.contrib.auth.models import User
from accounts.models import UserProfile


class ProfileForm(forms.ModelForm):
    """User profile edit form."""
    
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First Name',
        })
    )
    last_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last Name',
        })
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'email@example.com',
            'readonly': 'readonly',
        }),
        help_text='Use "Change Email" to update'
    )
    
    class Meta:
        model = UserProfile
        fields = ['company_name', 'designation', 'address_line1', 'address_line2', 'city', 'state', 'pincode', 'gstin']
        widgets = {
            'company_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Company / Organization',
            }),
            'designation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your Role / Designation',
            }),
            'address_line1': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Street Address',
            }),
            'address_line2': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Apartment, suite, etc. (optional)',
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'City',
            }),
            'state': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'State',
            }),
            'pincode': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'PIN Code',
                'maxlength': 6,
            }),
            'gstin': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '22AAAAA0000A1Z5',
                'maxlength': 15,
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email
    
    def save(self, commit=True):
        profile = super().save(commit=False)
        
        if self.user:
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name = self.cleaned_data['last_name']
            if commit:
                self.user.save()
        
        if commit:
            profile.save()
        
        return profile


class ChangePhoneForm(forms.Form):
    """Form to request phone number change."""
    
    new_phone = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+91 98765 43210',
            'autocomplete': 'tel',
        }),
        help_text='Enter your new phone number'
    )
    
    def clean_new_phone(self):
        phone = self.cleaned_data['new_phone']
        # Normalize phone number
        phone = ''.join(c for c in phone if c.isdigit() or c == '+')
        
        if len(phone) < 10:
            raise forms.ValidationError('Please enter a valid phone number.')
        
        # Check if already in use
        from accounts.models import UserProfile
        if UserProfile.objects.filter(phone=phone).exists():
            raise forms.ValidationError('This phone number is already registered.')
        
        return phone


class ChangeEmailForm(forms.Form):
    """Form to request email change."""
    
    new_email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'newemail@example.com',
            'autocomplete': 'email',
        }),
        help_text='Enter your new email address'
    )
    
    def clean_new_email(self):
        email = self.cleaned_data['new_email'].lower().strip()
        
        # Check if already in use
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email is already registered.')
        
        return email


class DeleteAccountForm(forms.Form):
    """Form to confirm account deletion."""
    
    confirm_text = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Type DELETE to confirm',
        }),
        help_text='Type DELETE to confirm account deletion'
    )
    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Why are you leaving? (optional)',
            'rows': 3,
        })
    )
    
    def clean_confirm_text(self):
        text = self.cleaned_data['confirm_text']
        if text.upper() != 'DELETE':
            raise forms.ValidationError('Please type DELETE to confirm.')
        return text


class NotificationPrefsForm(forms.Form):
    """Notification preferences form."""
    
    email_subscription_expiry = forms.BooleanField(
        required=False,
        label='Subscription expiry reminders',
        initial=True,
    )
    email_payment_receipts = forms.BooleanField(
        required=False,
        label='Payment receipts',
        initial=True,
    )
    email_product_updates = forms.BooleanField(
        required=False,
        label='Product updates & features',
        initial=True,
    )
    email_tips_tutorials = forms.BooleanField(
        required=False,
        label='Tips & tutorials',
        initial=False,
    )
    sms_otp = forms.BooleanField(
        required=False,
        label='SMS for OTP (required for login)',
        initial=True,
        disabled=True,
    )
