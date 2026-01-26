# datasets/migrations/0003_seed_states.py
"""
Seed initial Indian states for SOR rate management.
"""

from django.db import migrations


def seed_states(apps, schema_editor):
    """Create initial Indian states"""
    State = apps.get_model('datasets', 'State')
    
    states_data = [
        {
            'code': 'TS',
            'name': 'Telangana',
            'full_name': 'State of Telangana',
            'display_order': 1,
            'flag_icon': '🏛️',
            'is_active': True,
            'is_default': True,  # Telangana is the default
        },
        {
            'code': 'AP',
            'name': 'Andhra Pradesh',
            'full_name': 'State of Andhra Pradesh',
            'display_order': 2,
            'flag_icon': '🏛️',
            'is_active': True,
            'is_default': False,
        },
        {
            'code': 'KA',
            'name': 'Karnataka',
            'full_name': 'State of Karnataka',
            'display_order': 3,
            'flag_icon': '🏛️',
            'is_active': False,  # Not active yet, for future
            'is_default': False,
        },
        {
            'code': 'MH',
            'name': 'Maharashtra',
            'full_name': 'State of Maharashtra',
            'display_order': 4,
            'flag_icon': '🏛️',
            'is_active': False,
            'is_default': False,
        },
        {
            'code': 'TN',
            'name': 'Tamil Nadu',
            'full_name': 'State of Tamil Nadu',
            'display_order': 5,
            'flag_icon': '🏛️',
            'is_active': False,
            'is_default': False,
        },
        {
            'code': 'KL',
            'name': 'Kerala',
            'full_name': 'State of Kerala',
            'display_order': 6,
            'flag_icon': '🏛️',
            'is_active': False,
            'is_default': False,
        },
        {
            'code': 'GJ',
            'name': 'Gujarat',
            'full_name': 'State of Gujarat',
            'display_order': 7,
            'flag_icon': '🏛️',
            'is_active': False,
            'is_default': False,
        },
        {
            'code': 'RJ',
            'name': 'Rajasthan',
            'full_name': 'State of Rajasthan',
            'display_order': 8,
            'flag_icon': '🏛️',
            'is_active': False,
            'is_default': False,
        },
        {
            'code': 'MP',
            'name': 'Madhya Pradesh',
            'full_name': 'State of Madhya Pradesh',
            'display_order': 9,
            'flag_icon': '🏛️',
            'is_active': False,
            'is_default': False,
        },
        {
            'code': 'UP',
            'name': 'Uttar Pradesh',
            'full_name': 'State of Uttar Pradesh',
            'display_order': 10,
            'flag_icon': '🏛️',
            'is_active': False,
            'is_default': False,
        },
    ]
    
    for state_data in states_data:
        State.objects.get_or_create(
            code=state_data['code'],
            defaults=state_data
        )


def reverse_seed(apps, schema_editor):
    """Remove seeded states"""
    State = apps.get_model('datasets', 'State')
    State.objects.filter(code__in=['TS', 'AP', 'KA', 'MH', 'TN', 'KL', 'GJ', 'RJ', 'MP', 'UP']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('datasets', '0002_add_multistate_sor_support'),
    ]

    operations = [
        migrations.RunPython(seed_states, reverse_seed),
    ]
