#!/usr/bin/env python
"""Add AMC module to the database."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'estimate_site.settings')
django.setup()

from subscriptions.models import Module, ModulePricing

# Create AMC module
module_data = {
    'code': 'amc',
    'name': 'AMC',
    'description': 'Annual Maintenance Contract estimates with custom backend data',
    'url_name': 'amc_home',
    'icon': '📅',
    'color': '#8B5CF6',
    'display_order': 7,
    'features': ['Create AMC estimates', 'Custom backend data', 'Excel/MS Word Export', 'Multiple categories'],
}

module, created = Module.objects.update_or_create(
    code=module_data['code'],
    defaults=module_data
)

print(f"AMC module: {'created' if created else 'updated'}")

# Create pricing options
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
        defaults={'base_price': p['base_price'], 'sale_price': p['sale_price'], 'is_active': True}
    )
    print(f"  Pricing {p['duration_months']} months: ₹{p['sale_price']}")

print('\nAMC module setup complete!')
print(f'Total modules: {Module.objects.count()}')
