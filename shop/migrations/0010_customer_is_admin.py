# Згенеровано Django 6.0.1 2026-02-13 19:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0009_alter_order_status_review_reviewreply'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='is_admin',
            field=models.BooleanField(default=False, help_text='Позначте, щоб надати права адміністратора'),
        ),
    ]
