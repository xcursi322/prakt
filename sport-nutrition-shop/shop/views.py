from django.shortcuts import render, get_object_or_404, redirect
from django.http import FileResponse, JsonResponse
from django.template.loader import render_to_string
 
 
from .models import Product, OrderItem, Category, Order, Customer, Review, ReviewReply
from .forms import CheckoutForm, RegistrationForm, LoginForm, ProfileForm, ReviewForm, ReviewReplyForm


def _is_ajax_request(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


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

# Главная страница (приветственная)
def home(request):
    featured_products = Product.objects.all()[:6]  # Показываем 6 лучших товаров
    return render(request, 'shop/home.html', {
        'featured_products': featured_products
    })

# Доставка
def delivery(request):
    return render(request, 'shop/delivery.html')

# Каталог товаров
def catalog(request):
    from django.db.models import Avg
    products = Product.objects.all()
    categories = Category.objects.all()
    selected_category = None
    search_query = request.GET.get('q', '').strip()

    if search_query:
        products = products.filter(name__icontains=search_query)

    # Фильтрация по категории
    category_id = request.GET.get('category')
    if category_id:
        products = products.filter(category_id=category_id)
        selected_category = get_object_or_404(Category, id=category_id)

    # Сортировка по цене
    sort = request.GET.get('sort')
    if sort == 'price_asc':
        products = products.order_by('price')
    elif sort == 'price_desc':
        products = products.order_by('-price')
    elif sort == 'newest':
        products = products.order_by('-created_at')

    # Добавляем средний рейтинг к каждому продукту
    products = list(products)
    for p in products:
        avg_rating = p.reviews.aggregate_avg_rating if hasattr(p.reviews, 'aggregate_avg_rating') else None
        if avg_rating is None:
            avg_rating = p.reviews.aggregate(Avg('rating')).get('rating__avg')
        p.aggregate_avg_rating = int(round(avg_rating)) if avg_rating else 5

    if _is_ajax_request(request):
        products_html = render_to_string('shop/partials/catalog_products_grid.html', {
            'products': products,
        }, request=request)
        return JsonResponse({
            'success': True,
            'products_html': products_html,
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

# Детальная страница продукта
def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
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
        'customer_id': customer_id,
        'is_admin': is_admin
    })


# Добавление товара в корзину
def add_to_cart(request, product_id):
    if not request.session.get('customer_id'):
        # Если пользователь не авторизован, используем session ID для гостя
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

    cart = request.session.get('cart', {})  # получаем корзину из сессии
    cart[str(product_id)] = cart.get(str(product_id), 0) + quantity
    request.session['cart'] = cart
    request.session.modified = True  # обязательно для сохранения изменений

    if _is_ajax_request(request):
        total_count = 0
        for qty in cart.values():
            try:
                total_count += int(qty)
            except (TypeError, ValueError):
                continue
        return JsonResponse({'cart_count': total_count})

    next_url = request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('shop:catalog')


# Просмотр корзины
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

# Чекаут
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

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            # создаём заказ
            order = form.save(commit=False)
            order.total = total
            # привязываем заказ к текущему клиенту, если он авторизован
            customer_id = request.session.get('customer_id')
            if customer_id:
                try:
                    customer = Customer.objects.get(id=customer_id)
                    order.customer = customer
                except Customer.DoesNotExist:
                    pass
            order.save()

            # переносим товары из корзины в OrderItem
            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=item['product'],
                    quantity=item['quantity'],
                    price=item['product'].price
                )

            # очищаем корзину
            request.session['cart'] = {}
            request.session.modified = True

            return render(request, 'shop/checkout_success.html', {'order': order})
    else:
        form = CheckoutForm()

    return render(request, 'shop/checkout_form.html', {
        'form': form,
        'total': total
    })

# Увеличение количества товара в корзине
def increase_quantity(request, product_id):
    cart = request.session.get('cart', {})
    pid = str(product_id)

    if pid in cart:
        cart[pid] += 1

    request.session['cart'] = cart
    request.session.modified = True

    if _is_ajax_request(request):
        return JsonResponse(_build_cart_update_payload(cart, product_id))

    return redirect('shop:cart')

# Уменьшение количества товара в корзине
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

# Удаление товара из корзины
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

# Подача JS файла с фильтрами
def filters_js(request):
    from django.conf import settings
    js_file_path = settings.BASE_DIR / 'shop' / 'static' / 'shop' / 'filters.js'
    return FileResponse(open(js_file_path, 'rb'), content_type='application/javascript')

# Регистрация
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


# Вход
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
                    # Backward-compatibility: upgrade plaintext passwords on first login.
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


# Просмотр заказов пользователя
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


# Добавление отзыва к товару
def add_review(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    customer = request.session.get('customer_id')
    
    if not customer:
        return redirect('shop:login')
    
    customer = get_object_or_404(Customer, id=customer)
    
    # Проверяем, уже ли пользователь оставил отзыв на этот товар
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


# Удаление отзыва
def delete_review(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    customer = request.session.get('customer_id')
    
    if str(customer) != str(review.customer.id):
        return redirect('shop:product_detail', product_id=review.product.id)
    
    if request.method == 'POST':
        product_id = review.product.id
        review.delete()
        return redirect('shop:product_detail', product_id=product_id)
    
    return render(request, 'shop/delete_review.html', {'review': review})


# Добавление ответа админом на отзыв
def add_reply_to_review(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    admin_id = request.session.get('customer_id')
    
    if not admin_id:
        return redirect('shop:login')
    
    admin = get_object_or_404(Customer, id=admin_id)
    
    # Проверяем, является ли пользователь администратором
    if not admin.is_admin:
        return redirect('shop:product_detail', product_id=review.product.id)
    
    if request.method == 'POST':
        form = ReviewReplyForm(request.POST)
        if form.is_valid():
            reply = form.save(commit=False)
            reply.review = review
            reply.admin = admin
            reply.save()
            return redirect('shop:product_detail', product_id=review.product.id)
    else:
        form = ReviewReplyForm()
    
    return render(request, 'shop/add_reply.html', {
        'form': form,
        'review': review
    })


# Удаление ответа админом
def delete_reply(request, reply_id):
    reply = get_object_or_404(ReviewReply, id=reply_id)
    admin_id = request.session.get('customer_id')
    
    if not admin_id or str(admin_id) != str(reply.admin.id):
        return redirect('shop:product_detail', product_id=reply.review.product.id)
    
    admin = get_object_or_404(Customer, id=admin_id)
    
    # Проверяем администраторские права
    if not admin.is_admin:
        return redirect('shop:product_detail', product_id=reply.review.product.id)
    
    if request.method == 'POST':
        product_id = reply.review.product.id
        reply.delete()
        return redirect('shop:product_detail', product_id=product_id)
    
    return render(request, 'shop/delete_reply.html', {'reply': reply})