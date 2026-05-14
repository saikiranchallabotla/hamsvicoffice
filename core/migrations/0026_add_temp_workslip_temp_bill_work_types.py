from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_alter_usergrouporder_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='savedwork',
            name='work_type',
            field=models.CharField(choices=[
                ('new_estimate', 'Estimate'),
                ('workslip', 'Workslip'),
                ('bill', 'Bill'),
                ('temporary_works', 'Temporary Works'),
                ('temp_workslip', 'Temp Workslip'),
                ('temp_bill', 'Temp Bill'),
                ('amc', 'AMC Module'),
            ], max_length=30),
        ),
    ]
