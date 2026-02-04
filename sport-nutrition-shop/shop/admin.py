from django.contrib import admin
from .models import Product, Order, OrderItem, Category, Customer

admin.site.register(Category)
admin.site.register(Customer)

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