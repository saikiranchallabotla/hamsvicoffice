from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0026_add_temp_workslip_temp_bill_work_types"),
    ]

    operations = [
        migrations.AddField(
            model_name="savedwork",
            name="status_tracking",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
