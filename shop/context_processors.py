from .models import Category


def cart_count(request):
    cart = request.session.get('cart', {})
    total_count = 0
    for quantity in cart.values():
        try:
            total_count += int(quantity)
        except (TypeError, ValueError):
            continue
    return {'cart_count': total_count}


def global_categories(request):
    """Додає батьківські категорії до контексту для відображення в header"""
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories')
    return {'parent_categories': categories}
