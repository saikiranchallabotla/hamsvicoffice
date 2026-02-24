"""
Add file_data BinaryField and file_name to ModuleBackend for database-backed
file persistence across ephemeral filesystem redeployments.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0004_add_module_backend'),
    ]

    operations = [
        migrations.AddField(
            model_name='modulebackend',
            name='file_data',
            field=models.BinaryField(
                blank=True,
                editable=False,
                help_text='Binary copy of the backend file stored in DB for persistence',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='modulebackend',
            name='file_name',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Original filename for restoration',
                max_length=255,
            ),
        ),
    ]
