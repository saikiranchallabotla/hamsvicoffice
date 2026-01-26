"""
Management command to seed modules.
Run: python manage.py seed_modules
"""
from django.core.management.base import BaseCommand
from subscriptions.models import Module, ModulePricing


class Command(BaseCommand):
    help = 'Seed initial modules and pricing'

    def handle(self, *args, **options):
        modules_data = [
            {
                'code': 'new_estimate',
                'name': 'New Estimate',
                'description': 'Create new professional estimates for clients',
                'url_name': 'datas',
                'icon': '📝',
                'color': '#3B82F6',
                'display_order': 1,
                'features': ['Create estimates', 'Excel/MS Word Export', 'Share via link', 'Multiple formats'],
            },
            {
                'code': 'estimate',
                'name': 'Estimate',
                'description': 'Manage and view your estimates',
                'url_name': 'estimate',
                'icon': '📊',
                'color': '#6366F1',
                'display_order': 2,
                'features': ['View estimates', 'Edit estimates', 'Excel/MS Word Export'],
            },
            {
                'code': 'workslip',
                'name': 'Workslip',
                'description': 'Generate work slips for your projects',
                'url_name': 'workslip',
                'icon': '📋',
                'color': '#10B981',
                'display_order': 3,
                'features': ['Create workslips', 'Excel/MS Word Export', 'Track progress'],
            },
            {
                'code': 'bill',
                'name': 'Bill',
                'description': 'Create and manage bills for your business',
                'url_name': 'bill',
                'icon': '💰',
                'color': '#F59E0B',
                'display_order': 4,
                'features': ['Generate bills', 'Excel/MS Word Export', 'Payment tracking'],
            },
            {
                'code': 'self_formatted',
                'name': 'Self Formatted',
                'description': 'Create custom formatted documents',
                'url_name': 'self_formatted_form_page',
                'icon': '📄',
                'color': '#8B5CF6',
                'display_order': 5,
                'features': ['Custom templates', 'Flexible layouts', 'Excel/MS Word Export'],
            },
            {
                'code': 'temp_works',
                'name': 'Temporary Works',
                'description': 'Manage temporary works and projects',
                'url_name': 'tempworks_home',
                'icon': '🔧',
                'color': '#EF4444',
                'display_order': 6,
                'features': ['Temporary project management', 'Excel/MS Word Export', 'Quick access'],
            },
            {
                'code': 'amc',
                'name': 'AMC',
                'description': 'Annual Maintenance Contract estimates with custom backend data',
                'url_name': 'amc_home',
                'icon': '📅',
                'color': '#8B5CF6',
                'display_order': 7,
                'features': ['Create AMC estimates', 'Custom backend data', 'Excel/MS Word Export', 'Multiple categories'],
            },
        ]

        for data in modules_data:
            module, created = Module.objects.update_or_create(
                code=data['code'],
                defaults=data
            )
            self.stdout.write(f"{'Created' if created else 'Updated'}: {module.name}")
            
            # Create pricing
            pricing_options = [
                {'duration_months': 1, 'base_price': 349, 'sale_price': 299},
                {'duration_months': 3, 'base_price': 899, 'sale_price': 799},
                {'duration_months': 6, 'base_price': 1699, 'sale_price': 1499},
                {'duration_months': 12, 'base_price': 2999, 'sale_price': 2699},
            ]
            
            for p in pricing_options:
                ModulePricing.objects.update_or_create(
                    module=module,
                    duration_months=p['duration_months'],
                    defaults={
                        'base_price': p['base_price'],
                        'sale_price': p['sale_price'],
                    }
                )

        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {len(modules_data)} modules with pricing!'))
