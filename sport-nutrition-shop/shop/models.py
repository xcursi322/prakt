from django.db import models
import hashlib

STATUS_CHOICES = [
    ('new', 'Новий'),
    ('processing', 'В обробці'),
    ('shipped', 'Відправлено'),
    ('completed', 'Виконано'),
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
    is_admin = models.BooleanField(default=False, help_text='Позначте, щоб надати права адміністратора')

    def __str__(self):
        return f"{self.username} ({self.email})"

    def set_password(self, raw_password):
        """Хеширование пароля"""
        self.password = hashlib.sha256(raw_password.encode()).hexdigest()

    def check_password(self, raw_password):
        """Проверка пароля"""
        return self.password == hashlib.sha256(raw_password.encode()).hexdigest()

class Category(models.Model):
    name = models.CharField(max_length=200)  # Название категории
    description = models.TextField(blank=True)  # Описание категории
    
    class Meta:
        verbose_name_plural = "Categories"
    
    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200)       # Название товара
    brand = models.CharField(max_length=100, default="ALLNUTRITION", blank=True)  # Бренд
    weight = models.PositiveIntegerField(default=0, help_text="Вес в граммах")
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Цена
    old_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Старая цена")
    discount = models.PositiveIntegerField(default=0, help_text="Скидка в процентах")
    is_gift = models.BooleanField(default=False, help_text="Подарунок")
    is_bestseller = models.BooleanField(default=False, help_text="Bestseller")
    rating_count = models.PositiveIntegerField(default=0, help_text="Количество отзывов/рейтинг")
    description = models.TextField()              # Описание
    image = models.ImageField(upload_to='products/', blank=True, null=True)  # Картинка
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')  # Категория
    created_at = models.DateTimeField(auto_now_add=True)  # Дата создания

    def __str__(self):
        return self.name


class CartItem(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def total_price(self):
        return self.product.price * self.quantity
    
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
    payment_method = models.CharField(max_length=20, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')

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
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def total_price(self):
        # если quantity или price None, возвращаем 0
        qty = self.quantity if self.quantity is not None else 0
        prc = self.price if self.price is not None else 0
        return qty * prc

    def __str__(self):
        return f"{self.product.name} x {self.quantity or 0}"


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
    admin = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='review_replies')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return str(f"Reply to review {self.review.id}")
