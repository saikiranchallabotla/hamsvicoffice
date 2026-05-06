from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_alter_savedwork_work_type'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserGroupOrder',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scope', models.CharField(choices=[('estimate', 'Estimate'), ('amc', 'AMC'), ('temp', 'Temporary Works')], max_length=16)),
                ('category', models.CharField(max_length=32)),
                ('order', models.JSONField(default=list)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=models.CASCADE, related_name='group_orders', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('user', 'scope', 'category')},
            },
        ),
    ]
