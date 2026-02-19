from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_userdocumenttemplate_file_data_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='savedwork',
            name='bill_number',
            field=models.IntegerField(default=1, help_text='Bill number for multi-bill generation'),
        ),
        migrations.AddField(
            model_name='savedwork',
            name='bill_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('first_part', 'First & Part Bill'),
                    ('first_final', 'First & Final Bill'),
                    ('nth_part', 'Nth & Part Bill'),
                    ('nth_final', 'Nth & Final Bill'),
                ],
                default='',
                help_text='Type of bill (part/final)',
                max_length=30,
            ),
        ),
    ]
