from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = 'User Accounts & Authentication'
    
    def ready(self):
        """Register signal handlers when app is ready"""
        import accounts.signals  # noqa
