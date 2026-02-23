# Згенеровано Django 6.0.1 2026-01-23 18:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0005_order_status_alter_orderitem_price_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='products/'),
        ),
    ]
