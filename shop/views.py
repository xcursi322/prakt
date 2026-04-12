from django.shortcuts import render, get_object_or_404, redirect
from django.http import FileResponse, JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.db import transaction
from django.db.models import F, Avg, Sum
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt


from .models import Product, OrderItem, Category, Order, Customer, Review, ProductFlavor, PendingCheckout
from .forms import CheckoutForm, RegistrationForm, LoginForm, ProfileForm, ReviewForm
from . import liqpay as liqpay_helper


def _is_ajax_request(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def _get_delivery_cost(subtotal, delivery_method):
    if delivery_method == 'courier_kyiv':
        return 0 if subtotal >= 2000 else 120
    return 0 if subtotal >= 1500 else 70


def _build_cart_update_payload(cart, product_id):
    total = 0
    cart_count = 0
    target_quantity = 0
    target_subtotal = 0

    # Get all product IDs from cart
    product_ids = set()
    for cart_key in cart.keys():
        parts = str(cart_key).split('_')
        product_ids.add(int(parts[0]))
    
    products = {p.id: p for p in Product.objects.filter(id__in=product_ids)}
    
    # Calculate totals
    for cart_key, quantity in cart.items():
        parts = str(cart_key).split('_')
        pid = int(parts[0])
        product = products.get(pid)
        
        if product:
            quantity = int(quantity or 0)
            subtotal = product.price * quantity
            total += subtotal
            cart_count += quantity
            
            if pid == int(product_id):
                target_quantity += quantity
                target_subtotal += subtotal

    shipping_cost = _get_delivery_cost(total, 'np_branch')
    grand_total = total + shipping_cost

    return {
        'success': True,
        'product_id': int(product_id),
        'quantity': target_quantity,
        'subtotal': float(target_subtotal),
        'total': float(total),
        'shipping_cost': float(shipping_cost),
        'grand_total': float(grand_total),
        'free_shipping_threshold': 1500,
        'cart_count': cart_count,
        'is_free_shipping': shipping_cost == 0,
        'removed': target_quantity <= 0,
        'empty': cart_count == 0,
    }

# Головна сторінка
def home(request):
    popular_products = list(
        Product.objects
        .annotate(total_sold=Sum('orderitem__quantity'))
        .filter(total_sold__gt=0)
        .order_by('-total_sold', '-created_at')[:3]
    )

    if len(popular_products) < 3:
        existing_ids = [product.id for product in popular_products]
        fallback_products = list(
            Product.objects
            .exclude(id__in=existing_ids)
            .order_by('-created_at')[: 3 - len(popular_products)]
        )
        featured_products = popular_products + fallback_products
    else:
        featured_products = popular_products

    return render(request, 'shop/home.html', {
        'featured_products': featured_products
    })

# Доставка
def delivery(request):
    return render(request, 'shop/delivery.html')

# Каталог товарів
def catalog(request):
    import json
    from django.db.models import Avg, Count, Q
    products = Product.objects.all()
    categories = Category.objects.filter(parent__isnull=True)  # Тільки батьківські категорії
    selected_category = None
    search_query = request.GET.get('q', '').strip()

    if search_query:
        products = products.filter(name__icontains=search_query)

    # Фільтрація за категорією (з урахуванням підкатегорій)
    category_id = request.GET.get('category')
    if category_id:
        try:
            selected_category = Category.objects.get(id=category_id)
            if selected_category.is_parent():
                all_subcategories = selected_category.get_all_subcategories()
                category_ids = [selected_category.id] + [cat.id for cat in all_subcategories]
                products = products.filter(Q(category_id__in=category_ids))
            else:
                # Якщо вибрана підкатегорія, показати тільки товари з неї
                products = products.filter(category_id=category_id)
        except Category.DoesNotExist:
            selected_category = None

    # Сортування за ціною
    sort = request.GET.get('sort')
    if sort == 'price_asc':
        products = products.order_by('price')
    elif sort == 'price_desc':
        products = products.order_by('-price')
    elif sort == 'newest':
        products = products.order_by('-created_at')

    # Додаємо середній рейтинг до кожного продукту
    products = list(products)
    for p in products:
        rating_stats = p.reviews.aggregate(avg_rating=Avg('rating'), review_count=Count('id'))
        avg_rating = rating_stats.get('avg_rating')
        p.aggregate_avg_rating = int(round(avg_rating)) if avg_rating is not None else 0
        p.review_count = rating_stats.get('review_count') or 0
        flavors_qs = p.flavors.filter(stock_quantity__gt=0).select_related('flavor')
        p.flavors_json = json.dumps([
            {'id': pf.id, 'name': pf.flavor.name, 'color': pf.flavor.hex_color, 'stock': pf.stock_quantity}
            for pf in flavors_qs
        ], ensure_ascii=False)

    if _is_ajax_request(request):
        products_html = render_to_string('shop/partials/catalog_products_grid.html', {
            'products': products,
        }, request=request)
        hero_html = render_to_string('shop/partials/catalog_hero.html', {
            'selected_category': selected_category,
        }, request=request)
        return JsonResponse({
            'success': True,
            'products_html': products_html,
            'hero_html': hero_html,
            'products_count': len(products),
        })

    return render(request, 'shop/catalog.html', {
        'products': products,
        'categories': categories,
        'selected_category': selected_category,
        'selected_category_id': category_id,
        'selected_sort': sort,
        'selected_query': search_query
    })

# Детальна сторінка продукту
def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    reviews = product.reviews.select_related('customer').prefetch_related('replies')
    review_count = reviews.count()
    rating_stats = reviews.aggregate(avg_rating=Avg('rating'))
    avg_rating = rating_stats.get('avg_rating')
    aggregate_avg_rating = int(round(avg_rating)) if avg_rating is not None else 0
    min_delivery_cost = min(
        _get_delivery_cost(product.price, 'np_branch'),
        _get_delivery_cost(product.price, 'courier_kyiv')
    )
    delivery_is_free = min_delivery_cost == 0
    related_products = Product.objects.exclude(id=product.id).order_by('-created_at')[:8]
    customer_id = request.session.get('customer_id')
    is_admin = False
    
    # Получение вкусов для товара
    product_flavors = product.flavors.select_related('flavor').order_by('flavor__name')
    available_stock = product.get_available_stock()
    
    if customer_id:
        try:
            customer = Customer.objects.get(id=customer_id)
            is_admin = customer.is_admin
        except Customer.DoesNotExist:
            pass
    
    return render(request, 'shop/product_detail.html', {
        'product': product,
        'reviews': reviews,
        'review_count': review_count,
        'aggregate_avg_rating': aggregate_avg_rating,
        'min_delivery_cost': min_delivery_cost,
        'delivery_is_free': delivery_is_free,
        'related_products': related_products,
        'customer_id': customer_id,
        'is_admin': is_admin,
        'product_flavors': product_flavors,
        'available_stock': available_stock
    })


# Додавання товару в кошик
def add_to_cart(request, product_id):
    if not request.session.get('customer_id'):
        # Якщо користувач не авторизований, використовуємо session ID для гостя
        request.session['guest_session'] = request.session.session_key

    quantity = 1
    if request.method == 'POST':
        try:
            quantity = int(request.POST.get('quantity', 1))
        except (TypeError, ValueError):
            quantity = 1
    elif request.method == 'GET':
        try:
            quantity = int(request.GET.get('quantity', 1))
        except (TypeError, ValueError):
            quantity = 1

    if quantity < 1:
        quantity = 1

    product = get_object_or_404(Product, id=product_id)
    
    # Получение выбранного вкуса
    flavor_id = None
    product_flavor = None
    
    if request.method == 'POST':
        requested_flavor_id = request.POST.get('flavor_id')
    else:
        requested_flavor_id = request.GET.get('flavor_id')
    
    if requested_flavor_id:
        try:
            product_flavor = ProductFlavor.objects.get(
                id=requested_flavor_id,
                product_id=product_id
            )
            flavor_id = requested_flavor_id
        except ProductFlavor.DoesNotExist:
            if _is_ajax_request(request):
                return JsonResponse({
                    'success': False,
                    'message': 'Вибраний вкус невірний',
                    'cart_count': sum(int(qty or 0) for qty in request.session.get('cart', {}).values()),
                }, status=400)
            return redirect('shop:product_detail', product_id=product_id)

    cart = request.session.get('cart', {})  # отримуємо кошик із сесії

    # Якщо товар має вкуси але жодного не вибрано — повертаємо помилку
    has_flavors = ProductFlavor.objects.filter(product_id=product_id).exists()
    if has_flavors and not flavor_id:
        if _is_ajax_request(request):
            return JsonResponse({
                'success': False,
                'message': 'Будь ласка, оберіть смак',
                'cart_count': sum(int(qty or 0) for qty in cart.values()),
            }, status=400)
        next_url = request.META.get('HTTP_REFERER')
        return redirect(next_url) if next_url else redirect('shop:product_detail', product_id=product_id)

    # Формируем ключ кошика: product_id или product_id_flavor_id
    if flavor_id:
        cart_key = f"{product_id}_{flavor_id}"
    else:
        cart_key = str(product_id)
    
    existing_quantity = int(cart.get(cart_key, 0) or 0)
    
    # Получаем доступное количество товара
    available_stock = product.get_available_stock()
    
    # Проверяем наличие товара
    if available_stock <= 0:
        if _is_ajax_request(request):
            return JsonResponse({
                'success': False,
                'message': 'Товар закінчився',
                'cart_count': sum(int(qty or 0) for qty in cart.values()),
            }, status=400)
        next_url = request.META.get('HTTP_REFERER')
        if next_url:
            return redirect(next_url)
        return redirect('shop:catalog')
    
    # Проверка наличия конкретного вкуса если он выбран
    if product_flavor and product_flavor.stock_quantity <= 0:
        if _is_ajax_request(request):
            return JsonResponse({
                'success': False,
                'message': 'Вибраний вкус закінчився',
                'cart_count': sum(int(qty or 0) for qty in cart.values()),
            }, status=400)
        next_url = request.META.get('HTTP_REFERER')
        if next_url:
            return redirect(next_url)
        return redirect('shop:product_detail', product_id=product_id)

    # Определяем максимальное количество, которое можно добавить
    if product_flavor:
        allowed_to_add = max(product_flavor.stock_quantity - existing_quantity, 0)
    else:
        allowed_to_add = max(available_stock - existing_quantity, 0)
    
    if allowed_to_add <= 0:
        if _is_ajax_request(request):
            return JsonResponse({
                'success': False,
                'message': 'В кошику вже максимальна кількість для цього товару',
                'cart_count': sum(int(qty or 0) for qty in cart.values()),
            }, status=400)
        return redirect('shop:cart')

    actual_add = min(quantity, allowed_to_add)
    cart[cart_key] = existing_quantity + actual_add
    request.session['cart'] = cart
    request.session.modified = True  # обов'язково для збереження змін

    if _is_ajax_request(request):
        total_count = 0
        for qty in cart.values():
            try:
                total_count += int(qty)
            except (TypeError, ValueError):
                continue
        payload = {'success': True, 'cart_count': total_count}
        if actual_add < quantity:
            payload['message'] = 'Додано тільки доступну кількість товару'
        return JsonResponse(payload)

    next_url = request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('shop:catalog')


# Перегляд кошика
def cart(request):
    cart = request.session.get('cart', {})

    cart_items = []
    total = 0

    # Получаем все ID продуктов и вкусов
    product_ids = set()
    flavor_ids = set()
    
    for cart_key in cart.keys():
        parts = str(cart_key).split('_')
        if len(parts) == 2:
            # Это product_id_flavor_id
            product_ids.add(int(parts[0]))
            flavor_ids.add(int(parts[1]))
        else:
            # Это просто product_id
            product_ids.add(int(parts[0]))
    
    # Получаем все продукты и вкусы сразу
    products = {p.id: p for p in Product.objects.filter(id__in=product_ids)}
    product_flavors = {pf.id: pf for pf in ProductFlavor.objects.filter(id__in=flavor_ids).select_related('flavor')}
    
    for cart_key, quantity in cart.items():
        parts = str(cart_key).split('_')
        
        if len(parts) == 2:
            # Это product_id_flavor_id
            product_id = int(parts[0])
            flavor_id = int(parts[1])
            product = products.get(product_id)
            product_flavor = product_flavors.get(flavor_id)
            
            if product and product_flavor:
                subtotal = product.price * quantity
                cart_items.append({
                    'product': product,
                    'product_flavor': product_flavor,
                    'flavor': product_flavor.flavor,
                    'quantity': quantity,
                    'subtotal': subtotal,
                    'cart_key': cart_key
                })
                total += subtotal
        else:

            product_id = int(parts[0])
            product = products.get(product_id)
            
            if product:
                subtotal = product.price * quantity
                cart_items.append({
                    'product': product,
                    'product_flavor': None,
                    'flavor': None,
                    'quantity': quantity,
                    'subtotal': subtotal,
                    'cart_key': cart_key
                })
                total += subtotal

    shipping_cost = _get_delivery_cost(total, 'np_branch')
    grand_total = total + shipping_cost

    return render(request, 'shop/cart.html', {
        'cart_items': cart_items,
        'total': total,
        'shipping_cost': shipping_cost,
        'grand_total': grand_total,
        'free_shipping_threshold': 1500,
        'is_free_shipping': shipping_cost == 0,
    })

# Оформлення замовлення
def checkout(request):
    cart = request.session.get('cart', {})
    if not cart:
        return redirect('shop:cart')

    # Парсуємо ключі кошика для отримання ID продуктів і смаків
    product_ids = set()
    cart_info = {}  # {cart_key: {'product_id': ..., 'flavor_id': ..., 'quantity': ...}}
    
    for cart_key, quantity in cart.items():
        parts = str(cart_key).split('_')
        if len(parts) == 2:
            product_id = int(parts[0])
            flavor_id = int(parts[1])
            cart_info[cart_key] = {'product_id': product_id, 'flavor_id': flavor_id, 'quantity': quantity}
            product_ids.add(product_id)
        else:
            product_id = int(parts[0])
            cart_info[cart_key] = {'product_id': product_id, 'flavor_id': None, 'quantity': quantity}
            product_ids.add(product_id)
    
    # Отримуємо продукти та смаки
    products = {p.id: p for p in Product.objects.filter(id__in=product_ids)}
    product_flavors = {pf.id: pf for pf in ProductFlavor.objects.filter(product_id__in=product_ids).select_related('flavor', 'product')}
    
    cart_items = []
    total = 0

    for cart_key, info in cart_info.items():
        product_id = info['product_id']
        flavor_id = info['flavor_id']
        quantity = info['quantity']
        
        product = products.get(product_id)
        if not product:
            continue
        
        product_flavor = None
        if flavor_id:
            product_flavor = product_flavors.get(flavor_id)
        
        subtotal = product.price * quantity
        total += subtotal
        cart_items.append({
            'product': product,
            'product_flavor': product_flavor,
            'flavor': product_flavor.flavor if product_flavor else None,
            'quantity': quantity,
            'subtotal': subtotal,
            'cart_key': cart_key
        })

    customer = None
    customer_id = request.session.get('customer_id')
    if customer_id:
        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            customer = None

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        selected_delivery_method = request.POST.get('delivery_method') or 'np_branch'
        shipping_cost = _get_delivery_cost(total, selected_delivery_method)
        grand_total = total + shipping_cost
        if form.is_valid():
            with transaction.atomic():
                stock_products = {
                    product.id: product
                    for product in Product.objects.select_for_update().filter(id__in=product_ids)
                }
                stock_flavors = {
                    pf.id: pf
                    for pf in ProductFlavor.objects.select_for_update().filter(product_id__in=product_ids)
                }

                out_of_stock_items = []
                for item in cart_items:
                    product = stock_products.get(item['product'].id)
                    requested_quantity = int(item['quantity'] or 0)
                    
                    if not product:
                        item_name = item['product'].name
                        if item['product_flavor']:
                            item_name += f" ({item['flavor'].name})"
                        out_of_stock_items.append(item_name)
                    elif item['product_flavor']:
                        # Перевіряємо наявність конкретного смаку
                        pf = stock_flavors.get(item['product_flavor'].id)
                        if not pf or requested_quantity > pf.stock_quantity:
                            out_of_stock_items.append(f"{item['product'].name} ({item['flavor'].name})")

                if out_of_stock_items:
                    form.add_error(
                        None,
                        'Недостатньо товару в наявності: ' + ', '.join(out_of_stock_items)
                    )
                else:
                    payment_method = form.cleaned_data.get('payment_method')

                    if payment_method == 'online':
                        # Online payment: store data in PendingCheckout only.
                        # Don't create Order yet, don't clear cart.
                        form_fields = [
                            'first_name', 'last_name', 'email', 'phone',
                            'address', 'city', 'postal_code', 'postal_branch',
                            'delivery_method', 'payment_method',
                        ]
                        pending = PendingCheckout.objects.create(
                            customer=customer,
                            form_data={f: request.POST.get(f, '') for f in form_fields},
                            cart_snapshot=dict(cart),
                            grand_total=grand_total,
                        )
                        return redirect('shop:liqpay_pay', token=str(pending.token))

                    # COD: create Order and items immediately
                    order = form.save(commit=False)
                    order.total = grand_total

                    if customer:
                        order.customer = customer

                        order_first_name = (order.first_name or '').strip()
                        order_last_name = (order.last_name or '').strip()
                        order_address = (order.address or '').strip()
                        order_city = (order.city or '').strip()
                        order_postal_code = (order.postal_code or '').strip()

                        customer_updates = []
                        if not (customer.first_name or '').strip() and order_first_name:
                            customer.first_name = order_first_name
                            customer_updates.append('first_name')

                        if not (customer.last_name or '').strip() and order_last_name:
                            customer.last_name = order_last_name
                            customer_updates.append('last_name')

                        if not (customer.address or '').strip() and order_address:
                            customer.address = order_address
                            customer_updates.append('address')

                        if not (customer.city or '').strip() and order_city:
                            customer.city = order_city
                            customer_updates.append('city')

                        if not (customer.postal_code or '').strip() and order_postal_code:
                            customer.postal_code = order_postal_code
                            customer_updates.append('postal_code')

                        if customer_updates:
                            customer.save(update_fields=customer_updates + ['updated_at'])

                    order.save()

                    for item in cart_items:
                        product = stock_products[item['product'].id]
                        quantity = int(item['quantity'] or 0)
                        old_flavor = item['product_flavor']
                        product_flavor = stock_flavors.get(old_flavor.id) if old_flavor else None

                        OrderItem.objects.create(
                            order=order,
                            product=product,
                            flavor=product_flavor,
                            quantity=quantity,
                            price=product.price,
                        )

                        if product_flavor:
                            ProductFlavor.objects.filter(id=product_flavor.id).update(
                                stock_quantity=F('stock_quantity') - quantity
                            )

                    request.session['cart'] = {}
                    request.session.modified = True

                    # Наложений платіж — одразу показуємо успіх
                    order.payment_status = 'cod'
                    order.save(update_fields=['payment_status'])
                    return render(request, 'shop/checkout_success.html', {'order': order})
    else:
        selected_delivery_method = 'np_branch'
        shipping_cost = _get_delivery_cost(total, selected_delivery_method)
        grand_total = total + shipping_cost
        form_initial = {}
        if customer:
            form_initial = {
                'first_name': customer.first_name or '',
                'last_name': customer.last_name or '',
                'email': customer.email or '',
                'phone': customer.phone or '',
                'address': customer.address or '',
                'city': customer.city or '',
                'postal_code': customer.postal_code or '',
                'delivery_method': selected_delivery_method,
            }
        form = CheckoutForm(initial=form_initial)

    return render(request, 'shop/checkout_form.html', {
        'form': form,
        'total': total,
        'shipping_cost': shipping_cost,
        'grand_total': grand_total,
    })

# Збільшення кількості товару в кошику
def increase_quantity(request, product_id):
    cart = request.session.get('cart', {})
    
    # Отримуємо flavor_id з параметрів
    if request.method == 'POST':
        flavor_id = request.POST.get('flavor_id')
    else:
        flavor_id = request.GET.get('flavor_id')
    
    if flavor_id:
        cart_key = f"{product_id}_{flavor_id}"
    else:
        cart_key = str(product_id)
    
    if cart_key in cart:
        product = get_object_or_404(Product, id=product_id)
        current_qty = int(cart[cart_key] or 0)
        
        # Перевіряємо ліміт кількості
        if flavor_id:
            try:
                product_flavor = ProductFlavor.objects.get(id=flavor_id, product_id=product_id)
                max_qty = product_flavor.stock_quantity
            except ProductFlavor.DoesNotExist:
                max_qty = product.get_available_stock()
        else:
            max_qty = product.get_available_stock()
        
        if current_qty < max_qty:
            cart[cart_key] = current_qty + 1
        elif _is_ajax_request(request):
            payload = _build_cart_update_payload(cart, product_id)
            payload.update({
                'success': False,
                'message': 'Досягнуто максимальну кількість в наявності'
            })
            return JsonResponse(payload, status=400)

    request.session['cart'] = cart
    request.session.modified = True

    if _is_ajax_request(request):
        return JsonResponse(_build_cart_update_payload(cart, product_id))

    return redirect('shop:cart')

# Зменшення кількості товару в кошику
def decrease_quantity(request, product_id):
    cart = request.session.get('cart', {})
    
    # Отримуємо flavor_id з параметрів
    if request.method == 'POST':
        flavor_id = request.POST.get('flavor_id')
    else:
        flavor_id = request.GET.get('flavor_id')
    
    # Формируем ключ
    if flavor_id:
        cart_key = f"{product_id}_{flavor_id}"
    else:
        cart_key = str(product_id)

    if cart_key in cart:
        cart[cart_key] -= 1
        if cart[cart_key] <= 0:
            del cart[cart_key]

    request.session['cart'] = cart
    request.session.modified = True

    if _is_ajax_request(request):
        return JsonResponse(_build_cart_update_payload(cart, product_id))

    return redirect('shop:cart')

# Видалення товару з кошика
def remove_from_cart(request, product_id):
    cart = request.session.get('cart', {})
    
    # Отримуємо flavor_id з параметрів
    if request.method == 'POST':
        flavor_id = request.POST.get('flavor_id')
    else:
        flavor_id = request.GET.get('flavor_id')
    
    # Формируем ключ
    if flavor_id:
        cart_key = f"{product_id}_{flavor_id}"
    else:
        cart_key = str(product_id)

    if cart_key in cart:
        del cart[cart_key]

    request.session['cart'] = cart
    request.session.modified = True

    if _is_ajax_request(request):
        return JsonResponse(_build_cart_update_payload(cart, product_id))

    return redirect('shop:cart')

# Віддача JS-файлу з фільтрами
def filters_js(request):
    from django.conf import settings
    js_file_path = settings.BASE_DIR / 'shop' / 'static' / 'shop' / 'filters.js'
    return FileResponse(open(js_file_path, 'rb'), content_type='application/javascript')

# Реєстрація
def register(request):
    if request.session.get('customer_id'):
        return redirect('shop:index')
    
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            customer = form.save()
            request.session['customer_id'] = customer.id
            request.session['customer_username'] = customer.username
            request.session.modified = True
            return redirect('shop:home')
    else:
        form = RegistrationForm()
    
    return render(request, 'shop/register.html', {'form': form})


# Вхід
def login_view(request):
    if request.session.get('customer_id'):
        return redirect('shop:home')
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            
            try:
                customer = Customer.objects.get(username=username)
                if customer.check_password(password) and customer.is_active:
                    request.session['customer_id'] = customer.id
                    request.session['customer_username'] = customer.username
                    request.session.modified = True
                    return redirect('shop:catalog')

                if customer.password == password and customer.is_active:
                    # Зворотна сумісність: оновлюємо паролі у відкритому вигляді під час першого входу.
                    customer.set_password(password)
                    customer.save(update_fields=['password', 'updated_at'])
                    request.session['customer_id'] = customer.id
                    request.session['customer_username'] = customer.username
                    request.session.modified = True
                    return redirect('shop:catalog')

                form.add_error(None, 'Неправильне ім\'я користувача або пароль')
            except Customer.DoesNotExist:
                form.add_error(None, 'Неправильне ім\'я користувача або пароль')
    else:
        form = LoginForm()
    
    return render(request, 'shop/login.html', {'form': form})


# Вихід
def logout_view(request):
    if 'customer_id' in request.session:
        del request.session['customer_id']
    if 'customer_username' in request.session:
        del request.session['customer_username']
    request.session.modified = True
    return redirect('shop:home')


# Перегляд замовлень користувача
def orders(request):
    customer_id = request.session.get('customer_id')
    if not customer_id:
        return redirect('shop:login')
    
    try:
        customer = Customer.objects.get(id=customer_id)
        user_orders = Order.objects.filter(customer=customer).order_by('-created_at')
        
        return render(request, 'shop/orders.html', {
            'orders': user_orders
        })
    except Customer.DoesNotExist:
        return redirect('shop:login')


# Профіль користувача
def profile(request):
    customer_id = request.session.get('customer_id')
    if not customer_id:
        return redirect('shop:login')
    
    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        return redirect('shop:login')
    
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            return render(request, 'shop/profile.html', {
                'form': form,
                'customer': customer,
                'success': 'Профіль успішно оновлений!'
            })
    else:
        form = ProfileForm(instance=customer)
    
    return render(request, 'shop/profile.html', {
        'form': form,
        'customer': customer
    })


# Додавання відгуку до товару
def add_review(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    customer = request.session.get('customer_id')
    
    if not customer:
        return redirect('shop:login')
    
    customer = get_object_or_404(Customer, id=customer)
    
    # Перевіряємо, чи вже користувач залишив відгук на цей товар
    existing_review = Review.objects.filter(product=product, customer=customer).first()
    is_edit = request.GET.get('edit') == '1' or request.method == 'POST'

    # Якщо відгук вже є і це не режим редагування — редирект назад
    if existing_review and not is_edit:
        return redirect(f"{reverse('shop:product_detail', kwargs={'product_id': product_id})}#review-{existing_review.id}")

    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=existing_review)
        if form.is_valid():
            review = form.save(commit=False)
            review.product = product
            review.customer = customer
            review.save()
            return redirect('shop:product_detail', product_id=product_id)
    else:
        form = ReviewForm(instance=existing_review)
    
    return render(request, 'shop/add_review.html', {
        'form': form,
        'product': product,
        'existing_review': existing_review
    })


# Видалення відгуку
def delete_review(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    customer_id = request.session.get('customer_id')

    if not customer_id:
        return redirect('shop:login')

    current_customer = get_object_or_404(Customer, id=customer_id)

    # Видалити може автор відгуку або адміністратор
    if review.customer_id != current_customer.id and not current_customer.is_admin:
        return redirect('shop:product_detail', product_id=review.product.id)

    if request.method == 'POST':
        product_id = review.product.id
        review.delete()
        return redirect('shop:product_detail', product_id=product_id)

    return render(request, 'shop/delete_review.html', {'review': review})





# ─── LiqPay helpers ────────────────────────────────────────────────────────────

def _create_order_from_pending(pending):
    """Creates Order + OrderItems from PendingCheckout data. Decrements stock."""
    form_data = pending.form_data
    cart = pending.cart_snapshot

    product_ids = set()
    cart_info = {}
    for cart_key, quantity in cart.items():
        parts = str(cart_key).split('_')
        product_id = int(parts[0])
        flavor_id = int(parts[1]) if len(parts) == 2 else None
        cart_info[cart_key] = {
            'product_id': product_id,
            'flavor_id': flavor_id,
            'quantity': int(quantity),
        }
        product_ids.add(product_id)

    with transaction.atomic():
        stock_products = {
            p.id: p
            for p in Product.objects.select_for_update().filter(id__in=product_ids)
        }
        stock_flavors = {
            pf.id: pf
            for pf in ProductFlavor.objects.select_for_update().filter(product_id__in=product_ids)
        }

        order = Order(
            customer=pending.customer,
            total=pending.grand_total,
            payment_method='online',
            payment_status='paid',
            status='processing',
            liqpay_token=str(pending.token),
            first_name=form_data.get('first_name', ''),
            last_name=form_data.get('last_name', ''),
            email=form_data.get('email', ''),
            phone=form_data.get('phone', ''),
            address=form_data.get('address', ''),
            city=form_data.get('city', ''),
            postal_code=form_data.get('postal_code', ''),
            postal_branch=form_data.get('postal_branch', ''),
            delivery_method=form_data.get('delivery_method', ''),
        )
        order.save()

        for cart_key, info in cart_info.items():
            product = stock_products.get(info['product_id'])
            if not product:
                continue
            pf = stock_flavors.get(info['flavor_id']) if info['flavor_id'] else None
            qty = info['quantity']
            OrderItem.objects.create(
                order=order,
                product=product,
                flavor=pf,
                quantity=qty,
                price=product.price,
            )
            if pf:
                ProductFlavor.objects.filter(id=pf.id).update(
                    stock_quantity=F('stock_quantity') - qty
                )

    return order


# ─── LiqPay views ─────────────────────────────────────────────────────────────

def liqpay_pay(request, token):
    """
    Показує сторінку з auto-submit формою до LiqPay.
    Юзер потрапляє сюди після оформлення замовлення з онлайн-оплатою.
    """
    pending = get_object_or_404(PendingCheckout, token=token)

    callback_url = request.build_absolute_uri(reverse('shop:liqpay_callback'))
    result_url = request.build_absolute_uri(
        reverse('shop:liqpay_result', kwargs={'token': str(token)})
    )

    form_data = liqpay_helper.build_checkout_form(
        public_key=settings.LIQPAY_PUBLIC_KEY,
        private_key=settings.LIQPAY_PRIVATE_KEY,
        order_id=str(pending.token),
        amount=pending.grand_total,
        description='Замовлення — Sport Nutrition Shop',
        server_url=callback_url,
        result_url=result_url,
        sandbox=settings.LIQPAY_SANDBOX,
    )

    return render(request, 'shop/liqpay_redirect.html', {
        'pending': pending,
        'liqpay': form_data,
    })


@csrf_exempt
def liqpay_callback(request):
    """
    Server-to-server callback від LiqPay.
    LiqPay надсилає POST із полями data та signature.
    """
    if request.method != 'POST':
        return HttpResponse(status=405)

    data = request.POST.get('data', '')
    signature = request.POST.get('signature', '')

    if not liqpay_helper.verify_callback(settings.LIQPAY_PRIVATE_KEY, data, signature):
        return HttpResponse('invalid signature', status=400)

    payload = liqpay_helper.decode_callback(data)
    order_id = payload.get('order_id')  # UUID token string
    status = payload.get('status')

    if status in ('success', 'sandbox'):
        # Guard: check if order was already created (e.g. by liqpay_result)
        if not Order.objects.filter(liqpay_token=str(order_id)).exists():
            try:
                pending = PendingCheckout.objects.get(token=order_id)
            except PendingCheckout.DoesNotExist:
                return HttpResponse('OK')  # already processed
            _create_order_from_pending(pending)
            pending.delete()

    return HttpResponse('OK')


@csrf_exempt
def liqpay_result(request, token):
    """
    Сторінка, на яку LiqPay перенаправляє юзера після оплати.
    LiqPay надсилає data+signature сюди — використовуємо це для
    оновлення статусу (особливо важливо при локальному тестуванні).
    """
    # If callback already created the order, just show success
    try:
        order = Order.objects.get(liqpay_token=str(token))
        request.session['cart'] = {}
        request.session.modified = True
        return render(request, 'shop/checkout_success.html', {'order': order})
    except Order.DoesNotExist:
        pass

    try:
        pending = PendingCheckout.objects.get(token=token)
    except PendingCheckout.DoesNotExist:
        return redirect('shop:home')

    data = request.POST.get('data', '')
    signature = request.POST.get('signature', '')

    if data and signature:
        if liqpay_helper.verify_callback(settings.LIQPAY_PRIVATE_KEY, data, signature):
            payload = liqpay_helper.decode_callback(data)
            status = payload.get('status')
            if status in ('success', 'sandbox'):
                order = _create_order_from_pending(pending)
                pending.delete()
                request.session['cart'] = {}
                request.session.modified = True
                return render(request, 'shop/checkout_success.html', {'order': order})
            elif status in ('failure', 'error', 'reversed'):
                # Payment failed — cart stays intact
                return redirect('shop:cart')

    # No valid data — redirect to cart as fallback
    return redirect('shop:cart')