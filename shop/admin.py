from django.contrib import admin
from django import forms
from django.db.models import Q

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
    list_display = ('name', 'price', 'old_price', 'stock_quantity', 'category', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('name', 'description')
    fields = ('name', 'price', 'old_price', 'stock_quantity', 'description', 'category', 'image')

# Щоб бачити товари всередині замовлення прямо в адмінці
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'price', 'total_price')
    fields = ('product', 'quantity', 'price', 'total_price')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'first_name', 'last_name', 'email', 'phone', 'delivery_method', 'total','status', 'created_at')
    list_filter = ('status', 'delivery_method', 'created_at',)
    search_fields = ('first_name', 'last_name', 'email', 'phone')
    readonly_fields = ('total', 'created_at')
    inlines = [OrderItemInline]  # показуємо всі товари прямо всередині замовлення

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj:
            readonly.append('customer')
        return tuple(readonly)


class ReviewReplyAdminForm(forms.ModelForm):
    class Meta:
        model = ReviewReply
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        admin_field = self.fields.get('admin')
        if not admin_field:
            return

        admin_queryset = Customer.objects.filter(is_admin=True, is_active=True)

        if self.instance and self.instance.pk and self.instance.admin_id:
            admin_queryset = Customer.objects.filter(
                Q(is_admin=True, is_active=True) | Q(pk=self.instance.admin_id)
            )

        admin_field.queryset = admin_queryset.order_by('username').distinct()

    def clean_admin(self):
        selected_admin = self.cleaned_data.get('admin')
        if selected_admin and not selected_admin.is_admin:
            raise forms.ValidationError('Для відповіді можна обрати лише адміністратора.')
        if selected_admin and not selected_admin.is_active:
            raise forms.ValidationError('Неактивного адміністратора обрати не можна.')
        return selected_admin


class ReviewReplyInline(admin.TabularInline):
    model = ReviewReply
    form = ReviewReplyAdminForm
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
    form = ReviewReplyAdminForm
    list_display = ('review', 'admin', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('text', 'review__title', 'admin__username')
    readonly_fields = ('review', 'created_at', 'updated_at')