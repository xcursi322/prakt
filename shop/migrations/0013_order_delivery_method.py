from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0012_order_address_order_city_order_postal_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='delivery_method',
            field=models.CharField(blank=True, choices=[('nova_poshta', 'Нова пошта'), ('courier', 'Курʼєром'), ('pickup', 'Самовивіз')], default='nova_poshta', max_length=20),
        ),
    ]
