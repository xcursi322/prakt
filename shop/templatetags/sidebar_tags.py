from django import template
from shop.models import Category

register = template.Library()


@register.simple_tag
def get_categories_with_subcategories():
    """Отримує всі батьківські категорії з їх підкатегоріями"""
    return Category.objects.filter(parent__isnull=True).prefetch_related('subcategories')
