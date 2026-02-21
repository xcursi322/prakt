from django.contrib import admin
from django import forms

from .models import Product, Order, OrderItem, Category, Customer, Review, ReviewReply

admin.site.register(Category)

class CustomerAdminForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Новий пароль',
        required=False,
        widget=forms.PasswordInput,
    )
    password2 = forms.CharField(
        label='Підтвердіть пароль',
        required=False,
        widget=forms.PasswordInput,
    )

    class Meta:
        model = Customer
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 or password2:
            if password1 != password2:
                raise forms.ValidationError('Паролі не збігаються')

        return cleaned_data

    def save(self, commit=True):
        customer = super().save(commit=False)
        password1 = self.cleaned_data.get('password1')

        if password1:
            customer.set_password(password1)

        if commit:
            customer.save()

        return customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    form = CustomerAdminForm
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_admin', 'is_active', 'created_at')
    list_filter = ('is_admin', 'is_active', 'created_at')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    readonly_fields = ('created_at', 'updated_at', 'password')
    fieldsets = (
        ('Основна інформація', {
            'fields': ('username', 'email', 'password')
        }),
        ('Скидання пароля', {
            'fields': ('password1', 'password2')
        }),
        ('Особисті дані', {
            'fields': ('first_name', 'last_name', 'phone', 'address', 'city', 'postal_code')
        }),
        ('Дозволи', {
            'fields': ('is_admin', 'is_active')
        }),
        ('Дати', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'category', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('name', 'description')
    fields = ('name', 'price', 'description', 'category', 'image')

# Чтобы видеть товары внутри заказа прямо в админке
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'price', 'total_price')
    fields = ('product', 'quantity', 'price', 'total_price')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'first_name', 'last_name', 'email', 'phone', 'total','status', 'created_at')
    list_filter = ('status', 'created_at',)
    search_fields = ('first_name', 'last_name', 'email', 'phone')
    readonly_fields = ('total', 'created_at')
    inlines = [OrderItemInline]  # показываем все товары прямо внутри заказа


class ReviewReplyInline(admin.TabularInline):
    model = ReviewReply
    extra = 1
    fields = ('admin', 'text', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('title', 'product', 'customer', 'rating', 'is_verified_purchase', 'created_at')
    list_filter = ('rating', 'created_at', 'is_verified_purchase')
    search_fields = ('title', 'text', 'product__name', 'customer__username')
    readonly_fields = ('customer', 'product', 'created_at', 'updated_at')
    inlines = [ReviewReplyInline]
    fieldsets = (
        ('Основна інформація', {
            'fields': ('product', 'customer', 'rating', 'title')
        }),
        ('Вміст', {
            'fields': ('text',)
        }),
        ('Додатково', {
            'fields': ('is_verified_purchase', 'helpful_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ReviewReply)
class ReviewReplyAdmin(admin.ModelAdmin):
    list_display = ('review', 'admin', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('text', 'review__title', 'admin__username')
    readonly_fields = ('review', 'created_at', 'updated_at')