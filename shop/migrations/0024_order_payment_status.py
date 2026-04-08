from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0023_remove_product_brand_remove_product_discount_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='payment_status',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('pending', 'Очікує оплати'),
                    ('paid', 'Оплачено'),
                    ('failed', 'Помилка оплати'),
                    ('cod', 'Оплата при отриманні'),
                ],
                default='pending',
            ),
        ),
    ]
