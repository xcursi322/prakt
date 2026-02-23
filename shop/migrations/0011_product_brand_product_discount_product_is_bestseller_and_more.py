# Згенеровано Django 6.0.1 2026-02-17 00:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0010_customer_is_admin'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='brand',
            field=models.CharField(blank=True, default='ALLNUTRITION', max_length=100),
        ),
        migrations.AddField(
            model_name='product',
            name='discount',
            field=models.PositiveIntegerField(default=0, help_text='Скидка в процентах'),
        ),
        migrations.AddField(
            model_name='product',
            name='is_bestseller',
            field=models.BooleanField(default=False, help_text='Bestseller'),
        ),
        migrations.AddField(
            model_name='product',
            name='is_gift',
            field=models.BooleanField(default=False, help_text='Подарунок'),
        ),
        migrations.AddField(
            model_name='product',
            name='old_price',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Старая цена', max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='product',
            name='rating_count',
            field=models.PositiveIntegerField(default=0, help_text='Количество отзывов/рейтинг'),
        ),
        migrations.AddField(
            model_name='product',
            name='weight',
            field=models.PositiveIntegerField(default=0, help_text='Вес в граммах'),
        ),
    ]
