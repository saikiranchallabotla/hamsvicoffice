"""
Add file_hash, version, and admin_locked fields to ModuleBackend
for non-destructive deployment safety.

- file_hash: SHA-256 hash for integrity comparison before overwrite
- version: Integer version counter incremented on each file change
- admin_locked: Boolean flag to protect admin-modified files from any automated overwrite
- last_verified_at: Timestamp of last integrity verification
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0005_modulebackend_file_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='modulebackend',
            name='file_hash',
            field=models.CharField(
                blank=True,
                default='',
                help_text='SHA-256 hash of the file content for integrity checks',
                max_length=64,
            ),
        ),
        migrations.AddField(
            model_name='modulebackend',
            name='version',
            field=models.PositiveIntegerField(
                default=1,
                help_text='File version counter, incremented on each update',
            ),
        ),
        migrations.AddField(
            model_name='modulebackend',
            name='admin_locked',
            field=models.BooleanField(
                default=False,
                help_text='If True, automated deployment will NEVER overwrite this file',
            ),
        ),
        migrations.AddField(
            model_name='modulebackend',
            name='last_verified_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='Last time file integrity was verified during deployment',
            ),
        ),
        migrations.AddField(
            model_name='modulebackend',
            name='source_type',
            field=models.CharField(
                blank=True,
                default='admin',
                help_text='Origin of this backend: admin (uploaded by admin), seed (initial seeding), static (from core/data)',
                max_length=20,
            ),
        ),
    ]
