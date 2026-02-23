# Згенеровано Django 6.0.1 2026-01-23 03:08

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0002_cartitem_order'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrderItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField()),
                ('price', models.DecimalField(decimal_places=2, max_digits=7)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='shop.order')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='shop.product')),
            ],
        ),
    ]
