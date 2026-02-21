def cart_count(request):
    cart = request.session.get('cart', {})
    total_count = 0
    for quantity in cart.values():
        try:
            total_count += int(quantity)
        except (TypeError, ValueError):
            continue
    return {'cart_count': total_count}
