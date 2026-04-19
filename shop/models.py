from django.db import models
import hashlib
import uuid

STATUS_CHOICES = [
    ('new', 'Новий'),
    ('processing', 'В обробці'),
    ('shipped', 'Відправлено'),
    ('completed', 'Виконано'),
]

PAYMENT_STATUS_CHOICES = [
    ('pending', 'Очікує оплати'),
    ('paid', 'Оплачено'),
    ('failed', 'Помилка оплати'),
    ('cod', 'Оплата при отриманні'),
]

DELIVERY_METHOD_CHOICES = [
    ('np_branch', 'Відділення НП'),
    ('courier_kyiv', 'Курʼєр по Києву'),
]

class Customer(models.Model):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.username} ({self.email})"

    def set_password(self, raw_password):
        self.password = hashlib.sha256(raw_password.encode()).hexdigest()

    def check_password(self, raw_password):
        return self.password == hashlib.sha256(raw_password.encode()).hexdigest()

class Category(models.Model):
    name = models.CharField(max_length=200) 
    description = models.TextField(blank=True)  
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='subcategories',
        help_text='Виберіть батьківську категорію (якщо це підкатегорія)'
    )  
    
    class Meta:
        verbose_name_plural = "Categories"
    
    def __str__(self):
        if self.parent:
            return f"{self.parent.name} → {self.name}"
        return self.name
    
    def is_parent(self):
        return self.subcategories.exists()
    
    def get_all_subcategories(self):
        subcats = list(self.subcategories.all())
        for subcat in self.subcategories.all():
            subcats.extend(subcat.get_all_subcategories())
        return subcats


class Product(models.Model):
    name = models.CharField(max_length=200)      
    stock_quantity = models.PositiveIntegerField(default=0, help_text="Кількість в наявності (використовується тільки якщо немає смаків)")
    description = models.TextField(blank=True)     
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')  # Категорія
    created_at = models.DateTimeField(auto_now_add=True)  

    def __str__(self):
        return self.name
    
    def get_available_stock(self):
        """Отримати доступне кількість товару на основі варіантів або загального stock_quantity"""
        from django.db.models import Sum
        if self.variants.exists():
            total = self.variants.aggregate(total=Sum('stock_quantity'))['total'] or 0
            return total
        # Якщо немає варіантів — повертаємо загальне кількість з поля
        return self.stock_quantity

    def get_min_price(self):
        first = self.variants.order_by('price').first()
        return first.price if first else 0

    @property
    def main_image(self):
        return self.extra_images.order_by('order').first()

    def get_all_images(self):
        return [extra.image.url for extra in self.extra_images.order_by('order')]


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='extra_images')
    image = models.ImageField(upload_to='products/')
    order = models.PositiveIntegerField(default=0, help_text='Порядок відображення (менше = раніше)')

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Фото {self.order} для {self.product.name}"


class CartItem(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey('ProductVariant', on_delete=models.SET_NULL, null=True, blank=True, related_name='cart_items')
    quantity = models.PositiveIntegerField(default=1)

    def total_price(self):
        price = self.variant.price if self.variant else self.product.price
        return price * self.quantity
    
    class Meta:
        unique_together = ['customer', 'product', 'variant']
    
class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    postal_branch = models.CharField(max_length=100, blank=True)
    delivery_method = models.CharField(max_length=20, choices=DELIVERY_METHOD_CHOICES, default='np_branch', blank=True)
    payment_method = models.CharField(max_length=20, blank=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    total = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')
    liqpay_token = models.CharField(max_length=64, blank=True, default='')

    def delivery_method_label(self):
        labels = {
            'np_branch': 'Відділення НП',
            'courier_kyiv': 'Курʼєр по Києву',
        }
        return labels.get(self.delivery_method, self.delivery_method)

    @property
    def items_subtotal(self):
        return self.total - self.shipping_cost

    def __str__(self):
        if self.first_name or self.last_name:
            return f"Замовлення #{self.id} - {self.first_name} {self.last_name}"
        elif self.email:
            return f"Замовлення #{self.id} - {self.email}"
        else:
            return f"Замовлення #{self.id} - Гість"

    
class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    variant = models.ForeignKey('ProductVariant', on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def total_price(self):
        qty = self.quantity if self.quantity is not None else 0
        prc = self.price if self.price is not None else 0
        return qty * prc

    def __str__(self):
        if self.variant:
            parts = []
            if self.variant.weight_label:
                parts.append(self.variant.weight_label)
            if self.variant.flavor:
                parts.append(self.variant.flavor.name)
            desc = ', '.join(parts) if parts else ''
            if desc:
                return f"{self.product.name} ({desc}) x {self.quantity or 0}"
        return f"{self.product.name} x {self.quantity or 0}"


class PendingCheckout(models.Model):
    """Тимчасове сховище даних замовлення до підтвердження оплати LiqPay."""
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    form_data = models.JSONField()        # поля форми checkout
    cart_snapshot = models.JSONField()   # копія session['cart']
    grand_total = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"PendingCheckout {self.token}"


class SiteVisit(models.Model):
    visit_date = models.DateField(auto_now_add=True)
    session_key = models.CharField(max_length=64)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Відвідування сайту'
        verbose_name_plural = 'Відвідування сайту'
        constraints = [
            models.UniqueConstraint(fields=['visit_date', 'session_key'], name='unique_daily_session_visit')
        ]

    def __str__(self):
        return f"{self.visit_date} - {self.session_key}"


class Review(models.Model):
    RATING_CHOICES = [
        (1, '1 - Дуже погано'),
        (2, '2 - Погано'),
        (3, '3 - Задовільно'),
        (4, '4 - Добре'),
        (5, '5 - Відмінно'),
    ]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(choices=RATING_CHOICES)
    title = models.CharField(max_length=200)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_verified_purchase = models.BooleanField(default=False)
    helpful_count = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['product', 'customer']
    
    def __str__(self):
        return f"{self.customer.username} - {self.product.name} ({self.rating}/5)"


class ReviewReply(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='replies')
    admin = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='review_replies'
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return str(f"Reply to review {self.review.id}")


class ProductVariant(models.Model):
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='variants')
    weight_label = models.CharField(max_length=20, blank=True, default='', help_text='Грамовка, наприклад: 500г, 1кг')
    flavor = models.ForeignKey('Flavor', on_delete=models.SET_NULL, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    old_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text='Стара ціна (якщо є знижка)')
    stock_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['id']
        unique_together = ['product', 'weight_label', 'flavor']

    def __str__(self):
        parts = [self.product.name]
        if self.weight_label:
            parts.append(self.weight_label)
        if self.flavor:
            parts.append(self.flavor.name)
        return ' - '.join(parts)

    def is_in_stock(self):
        return self.stock_quantity > 0


class Flavor(models.Model):
    name = models.CharField(max_length=30, unique=True)  
    hex_color = models.CharField(
        max_length=7,
        default='#9CA3AF'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

