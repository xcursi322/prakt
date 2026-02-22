from django.db import migrations


def normalize_delivery_methods(apps, schema_editor):
    Order = apps.get_model('shop', 'Order')
    mapping = {
        'nova_poshta': 'np_branch',
        'courier': 'courier_kyiv',
    }

    for legacy_value, normalized_value in mapping.items():
        Order.objects.filter(delivery_method=legacy_value).update(delivery_method=normalized_value)


def reverse_normalize_delivery_methods(apps, schema_editor):
    Order = apps.get_model('shop', 'Order')
    mapping = {
        'np_branch': 'nova_poshta',
        'courier_kyiv': 'courier',
    }

    for normalized_value, legacy_value in mapping.items():
        Order.objects.filter(delivery_method=normalized_value).update(delivery_method=legacy_value)


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0014_alter_order_delivery_method'),
    ]

    operations = [
        migrations.RunPython(normalize_delivery_methods, reverse_normalize_delivery_methods),
    ]
