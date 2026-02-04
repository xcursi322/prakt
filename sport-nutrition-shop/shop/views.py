from django.shortcuts import render, get_object_or_404, redirect
from django.http import FileResponse
from .models import Product, OrderItem, Category, Order, Customer
from .forms import CheckoutForm, RegistrationForm, LoginForm, ProfileForm

# Главная страница с каталогом
def index(request):
    products = Product.objects.all()
    categories = Category.objects.all()
    selected_category = None
    
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
    
    return render(request, 'shop/index.html', {
        'products': products,
        'categories': categories,
        'selected_category': selected_category,
        'selected_category_id': category_id,
        'selected_sort': sort
    })


# Детальная страница продукта
def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    return render(request, 'shop/product_detail.html', {'product': product})


# Добавление товара в корзину
def add_to_cart(request, product_id):
    if not request.session.get('customer_id'):
        # Если пользователь не авторизован, используем session ID для гостя
        request.session['guest_session'] = request.session.session_key
    
    cart = request.session.get('cart', {})  # получаем корзину из сессии
    cart[str(product_id)] = cart.get(str(product_id), 0) + 1
    request.session['cart'] = cart
    request.session.modified = True  # обязательно для сохранения изменений
    return redirect('shop:cart')


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
    return redirect('shop:cart')

# Удаление товара из корзины
def remove_from_cart(request, product_id):
    cart = request.session.get('cart', {})
    pid = str(product_id)

    if pid in cart:
        del cart[pid]

    request.session['cart'] = cart
    request.session.modified = True
    return redirect('shop:cart')

# Подача JS файла с фильтрами
def filters_js(request):
    from django.conf import settings
    js_file_path = settings.BASE_DIR / 'shop' / 'templates' / 'shop' / 'filters.js'
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
            return redirect('shop:index')
    else:
        form = RegistrationForm()
    
    return render(request, 'shop/register.html', {'form': form})


# Вход
def login_view(request):
    if request.session.get('customer_id'):
        return redirect('shop:index')
    
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
                    return redirect('shop:index')
                else:
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
    return redirect('shop:index')


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