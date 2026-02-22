from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0013_order_delivery_method'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='delivery_method',
            field=models.CharField(blank=True, choices=[('np_branch', 'Відділення НП'), ('courier_kyiv', 'Курʼєр по Києву')], default='np_branch', max_length=20),
        ),
    ]
