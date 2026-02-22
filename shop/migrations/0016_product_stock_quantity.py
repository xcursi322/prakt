from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0015_normalize_order_delivery_method_values'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='stock_quantity',
            field=models.PositiveIntegerField(default=50, help_text='Кількість в наявності'),
        ),
    ]
