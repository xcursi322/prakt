from django.shortcuts import render, get_object_or_404, redirect
from django.http import FileResponse, JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.db import transaction
from django.db.models import F, Avg
 
 
from .models import Product, OrderItem, Category, Order, Customer, Review, ReviewReply
from .forms import CheckoutForm, RegistrationForm, LoginForm, ProfileForm, ReviewForm, ReviewReplyForm


def _is_ajax_request(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def _get_delivery_cost(subtotal, delivery_method):
    if delivery_method == 'courier_kyiv':
        return 0 if subtotal >= 2000 else 120
    return 0 if subtotal >= 1500 else 70


def _build_cart_update_payload(cart, product_id):
    total = 0
    cart_count = 0
    target_quantity = int(cart.get(str(product_id), 0) or 0)
    target_subtotal = 0

    products = Product.objects.filter(id__in=cart.keys())
    for product in products:
        quantity = int(cart.get(str(product.id), 0) or 0)
        subtotal = product.price * quantity
        total += subtotal
        cart_count += quantity

        if product.id == int(product_id):
            target_subtotal = subtotal

    return {
        'success': True,
        'product_id': int(product_id),
        'quantity': target_quantity,
        'subtotal': float(target_subtotal),
        'total': float(total),
        'cart_count': cart_count,
        'removed': target_quantity <= 0,
        'empty': cart_count == 0,
    }

# Головна сторінка (вітальна)
def home(request):
    featured_products = Product.objects.all()[:6]  # Показуємо 6 найкращих товарів
    return render(request, 'shop/home.html', {
        'featured_products': featured_products
    })

# Доставка
def delivery(request):
    return render(request, 'shop/delivery.html')

# Каталог товарів
def catalog(request):
    from django.db.models import Avg, Count
    products = Product.objects.all()
    categories = Category.objects.all()
    selected_category = None
    search_query = request.GET.get('q', '').strip()

    if search_query:
        products = products.filter(name__icontains=search_query)

    # Фільтрація за категорією
    category_id = request.GET.get('category')
    if category_id:
        products = products.filter(category_id=category_id)
        selected_category = get_object_or_404(Category, id=category_id)

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
        'is_admin': is_admin
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

    cart = request.session.get('cart', {})  # отримуємо кошик із сесії
    existing_quantity = int(cart.get(str(product_id), 0) or 0)
    if product.stock_quantity <= 0:
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

    allowed_to_add = max(product.stock_quantity - existing_quantity, 0)
    if allowed_to_add <= 0:
        if _is_ajax_request(request):
            return JsonResponse({
                'success': False,
                'message': 'В кошику вже максимальна кількість для цього товару',
                'cart_count': sum(int(qty or 0) for qty in cart.values()),
            }, status=400)
        return redirect('shop:cart')

    actual_add = min(quantity, allowed_to_add)
    cart[str(product_id)] = existing_quantity + actual_add
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

    for product_id, quantity in cart.items():
        product = Product.objects.get(id=product_id)
        subtotal = product.price * quantity

        cart_items.append({
            'product': product,
            'quantity': quantity,
            'subtotal': subtotal
        })

        total += subtotal

    return render(request, 'shop/cart.html', {
        'cart_items': cart_items,
        'total': total
    })

# Оформлення замовлення
def checkout(request):
    cart = request.session.get('cart', {})
    if not cart:
        return redirect('shop:cart')

    products = Product.objects.filter(id__in=cart.keys())
    cart_items = []
    total = 0

    for product in products:
        quantity = cart.get(str(product.id), 0)
        subtotal = product.price * quantity
        total += subtotal
        cart_items.append({
            'product': product,
            'quantity': quantity,
            'subtotal': subtotal
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
                    for product in Product.objects.select_for_update().filter(id__in=cart.keys())
                }

                out_of_stock_items = []
                for item in cart_items:
                    fresh_product = stock_products.get(item['product'].id)
                    requested_quantity = int(item['quantity'] or 0)
                    if not fresh_product or requested_quantity > fresh_product.stock_quantity:
                        out_of_stock_items.append(item['product'].name)

                if out_of_stock_items:
                    form.add_error(
                        None,
                        'Недостатньо товару в наявності: ' + ', '.join(out_of_stock_items)
                    )
                else:
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
                        OrderItem.objects.create(
                            order=order,
                            product=product,
                            quantity=quantity,
                            price=product.price
                        )
                        Product.objects.filter(id=product.id).update(
                            stock_quantity=F('stock_quantity') - quantity
                        )

                    request.session['cart'] = {}
                    request.session.modified = True

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
    pid = str(product_id)

    if pid in cart:
        product = get_object_or_404(Product, id=product_id)
        current_qty = int(cart[pid] or 0)
        if current_qty < product.stock_quantity:
            cart[pid] = current_qty + 1
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
    pid = str(product_id)

    if pid in cart:
        cart[pid] -= 1
        if cart[pid] <= 0:
            del cart[pid]

    request.session['cart'] = cart
    request.session.modified = True

    if _is_ajax_request(request):
        return JsonResponse(_build_cart_update_payload(cart, product_id))

    return redirect('shop:cart')

# Видалення товару з кошика
def remove_from_cart(request, product_id):
    cart = request.session.get('cart', {})
    pid = str(product_id)

    if pid in cart:
        del cart[pid]

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

    admin = get_object_or_404(Customer, id=customer_id)

    if not admin.is_admin:
        return redirect('shop:product_detail', product_id=review.product.id)
    
    if request.method == 'POST':
        product_id = review.product.id
        review.delete()
        return redirect('shop:product_detail', product_id=product_id)
    
    return render(request, 'shop/delete_review.html', {'review': review})


# Додавання відповіді адміністратором на відгук
def add_reply_to_review(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    admin_id = request.session.get('customer_id')
    
    if not admin_id:
        return redirect('shop:login')
    
    admin = get_object_or_404(Customer, id=admin_id)
    
    # Перевіряємо, чи є користувач адміністратором
    if not admin.is_admin:
        return redirect('shop:product_detail', product_id=review.product.id)

    if request.method == 'GET':
        return redirect(f"{reverse('shop:product_detail', kwargs={'product_id': review.product.id})}#review-{review.id}")
    
    if request.method == 'POST':
        form = ReviewReplyForm(request.POST)
        if form.is_valid():
            reply = form.save(commit=False)
            reply.review = review
            reply.admin = admin
            reply.save()
            return redirect(f"{reverse('shop:product_detail', kwargs={'product_id': review.product.id})}#review-{review.id}")
    else:
        form = ReviewReplyForm()
    
    return render(request, 'shop/add_reply.html', {
        'form': form,
        'review': review
    })


# Видалення відповіді адміністратором
def delete_reply(request, reply_id):
    reply = get_object_or_404(ReviewReply, id=reply_id)
    admin_id = request.session.get('customer_id')
    
    if not admin_id or str(admin_id) != str(reply.admin.id):
        return redirect('shop:product_detail', product_id=reply.review.product.id)
    
    admin = get_object_or_404(Customer, id=admin_id)
    
    # Перевіряємо права адміністратора
    if not admin.is_admin:
        return redirect('shop:product_detail', product_id=reply.review.product.id)
    
    if request.method == 'POST':
        product_id = reply.review.product.id
        reply.delete()
        return redirect('shop:product_detail', product_id=product_id)
    
    return render(request, 'shop/delete_reply.html', {'reply': reply})