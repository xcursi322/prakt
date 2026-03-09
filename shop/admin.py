from django.contrib import admin
from django import forms
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth, TruncDay, TruncHour
from django.db.models import Q
from django.template.response import TemplateResponse
from django.urls import path
from datetime import date, datetime, time, timedelta
from django.utils import timezone

from .models import Product, Order, OrderItem, Category, Customer, Review, ReviewReply, SiteVisit, STATUS_CHOICES


UKR_MONTHS = {
    1: 'Січень',
    2: 'Лютий',
    3: 'Березень',
    4: 'Квітень',
    5: 'Травень',
    6: 'Червень',
    7: 'Липень',
    8: 'Серпень',
    9: 'Вересень',
    10: 'Жовтень',
    11: 'Листопад',
    12: 'Грудень',
}


def _shift_month_start(month_start, delta_months):
    month = month_start.month - 1 + delta_months
    year = month_start.year + month // 12
    month = month % 12 + 1
    return month_start.replace(year=year, month=month, day=1)


def _parse_selected_month(month_str):
    if not month_str:
        return None
    try:
        return datetime.strptime(month_str, '%Y-%m').date().replace(day=1)
    except ValueError:
        return None


def _parse_selected_month_from_request(request):
    direct_month = _parse_selected_month(request.GET.get('month'))
    if direct_month:
        return direct_month

    year_raw = request.GET.get('year')
    month_num_raw = request.GET.get('month_num')
    if not year_raw or not month_num_raw:
        return None

    try:
        year = int(year_raw)
        month_num = int(month_num_raw)
    except (TypeError, ValueError):
        return None

    if year < 2000 or year > 2100:
        return None
    if month_num < 1 or month_num > 12:
        return None

    return date(year, month_num, 1)


def _format_ukr_month(month_date):
    month_name = UKR_MONTHS.get(month_date.month, month_date.strftime('%m'))
    return f'{month_name} {month_date.year}'


def _normalize_month_bucket(bucket_value):
    if hasattr(bucket_value, 'date'):
        bucket_value = bucket_value.date()
    return bucket_value.replace(day=1)


def _build_period_axis(period, selected_month=None):
    now = timezone.localtime()

    if period == 'day':
        current_hour = now.replace(minute=0, second=0, microsecond=0)
        points = [current_hour - timedelta(hours=offset) for offset in range(23, -1, -1)]
        return {
            'points': points,
            'labels': [item.strftime('%H:%M') for item in points],
            'start_dt': points[0],
            'end_dt': current_hour + timedelta(hours=1),
            'period_label': 'день',
        }

    if period == 'week':
        today = now.date()
        points = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
        start_dt = timezone.make_aware(datetime.combine(points[0], time.min))
        return {
            'points': points,
            'labels': [item.strftime('%d.%m') for item in points],
            'start_dt': start_dt,
            'end_dt': timezone.make_aware(datetime.combine(today + timedelta(days=1), time.min)),
            'period_label': 'тиждень',
        }

    if period == 'year':
        month_start = now.date().replace(day=1)
        points = [_shift_month_start(month_start, -offset) for offset in range(11, -1, -1)]
        start_dt = timezone.make_aware(datetime.combine(points[0], time.min))
        return {
            'points': points,
            'labels': [_format_ukr_month(item) for item in points],
            'start_dt': start_dt,
            'end_dt': timezone.make_aware(datetime.combine(_shift_month_start(month_start, 1), time.min)),
            'period_label': 'рік',
        }

    month_start = selected_month or now.date().replace(day=1)
    month_end = _shift_month_start(month_start, 1)
    days_in_month = (month_end - month_start).days
    points = [month_start + timedelta(days=offset) for offset in range(days_in_month)]
    start_dt = timezone.make_aware(datetime.combine(month_start, time.min))
    return {
        'points': points,
        'labels': [item.strftime('%d.%m') for item in points],
        'start_dt': start_dt,
        'end_dt': timezone.make_aware(datetime.combine(month_end, time.min)),
        'period_label': 'місяць',
    }


def admin_statistics_view(request):
    period = (request.GET.get('period') or 'month').lower()
    if period not in {'day', 'week', 'month', 'year'}:
        period = 'month'

    selected_month = _parse_selected_month_from_request(request)
    effective_month = selected_month or timezone.localdate().replace(day=1)
    axis = _build_period_axis(period, selected_month=selected_month)
    points = axis['points']
    period_start_dt = axis['start_dt']
    period_end_dt = axis['end_dt']

    orders_period_qs = Order.objects.filter(created_at__gte=period_start_dt, created_at__lt=period_end_dt)
    visits_period_qs = SiteVisit.objects.filter(created_at__gte=period_start_dt, created_at__lt=period_end_dt)
    registered_visits_qs = visits_period_qs.filter(customer__isnull=False)

    if period == 'day':
        orders_grouped = (
            orders_period_qs
            .annotate(bucket=TruncHour('created_at'))
            .values('bucket')
            .annotate(orders_count=Count('id'), revenue_sum=Sum('total'))
            .order_by('bucket')
        )
        visits_grouped = (
            visits_period_qs
            .annotate(bucket=TruncHour('created_at'))
            .values('bucket')
            .annotate(visits_count=Count('session_key', distinct=True))
            .order_by('bucket')
        )

        orders_map = {
            item['bucket'].replace(minute=0, second=0, microsecond=0): item
            for item in orders_grouped
            if item.get('bucket')
        }
        visits_map = {
            item['bucket'].replace(minute=0, second=0, microsecond=0): item['visits_count']
            for item in visits_grouped
            if item.get('bucket')
        }
    elif period in {'week', 'month'}:
        orders_grouped = (
            orders_period_qs
            .annotate(bucket=TruncDay('created_at'))
            .values('bucket')
            .annotate(orders_count=Count('id'), revenue_sum=Sum('total'))
            .order_by('bucket')
        )
        visits_grouped = (
            SiteVisit.objects
            .filter(visit_date__gte=points[0], visit_date__lt=period_end_dt.date())
            .values('visit_date')
            .annotate(visits_count=Count('id'))
            .order_by('visit_date')
        )

        orders_map = {
            item['bucket'].date(): item
            for item in orders_grouped
            if item.get('bucket')
        }
        visits_map = {
            item['visit_date']: item['visits_count']
            for item in visits_grouped
            if item.get('visit_date')
        }
    else:
        orders_grouped = (
            orders_period_qs
            .annotate(bucket=TruncMonth('created_at'))
            .values('bucket')
            .annotate(orders_count=Count('id'), revenue_sum=Sum('total'))
            .order_by('bucket')
        )
        visits_grouped = (
            SiteVisit.objects
            .filter(visit_date__gte=points[0], visit_date__lt=period_end_dt.date())
            .annotate(bucket=TruncMonth('visit_date'))
            .values('bucket')
            .annotate(visits_count=Count('id'))
            .order_by('bucket')
        )

        orders_map = {
            _normalize_month_bucket(item['bucket']): item
            for item in orders_grouped
            if item.get('bucket')
        }
        visits_map = {
            _normalize_month_bucket(item['bucket']): item['visits_count']
            for item in visits_grouped
            if item.get('bucket')
        }

    chart_labels = axis['labels']
    orders_series = [int(orders_map.get(point, {}).get('orders_count', 0) or 0) for point in points]
    revenue_series = [float(orders_map.get(point, {}).get('revenue_sum', 0) or 0) for point in points]
    visits_series = [int(visits_map.get(point, 0) or 0) for point in points]

    status_map = dict(STATUS_CHOICES)
    status_breakdown = list(
        orders_period_qs
        .values('status')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    status_labels = [status_map.get(item['status'], item['status']) for item in status_breakdown]
    status_values = [item['count'] for item in status_breakdown]

    top_products = list(
        OrderItem.objects
        .filter(order__created_at__gte=period_start_dt, order__created_at__lt=period_end_dt)
        .values('product__name')
        .annotate(total_qty=Sum('quantity'))
        .order_by('-total_qty')[:5]
    )

    context = {
        **admin.site.each_context(request),
        'title': 'Статистика магазину',
        'selected_period': period,
        'selected_month': effective_month.strftime('%Y-%m'),
        'selected_month_label': _format_ukr_month(effective_month),
        'selected_year': effective_month.year,
        'selected_month_num': effective_month.month,
        'year_options': list(range(effective_month.year - 5, effective_month.year + 2)),
        'ukr_month_options': [
            {'value': month_num, 'label': month_name}
            for month_num, month_name in UKR_MONTHS.items()
        ],
        'period_label': axis['period_label'],
        'chart_labels': chart_labels,
        'orders_series': orders_series,
        'revenue_series': revenue_series,
        'visits_series': visits_series,
        'status_labels': status_labels,
        'status_values': status_values,
        'top_products': top_products,
        'total_visits': sum(visits_series),
        'registered_visits': registered_visits_qs.count(),
        'registered_users_count': registered_visits_qs.values('customer_id').distinct().count(),
        'total_orders': orders_period_qs.count(),
        'total_revenue': orders_period_qs.aggregate(total=Sum('total')).get('total') or 0,
    }
    return TemplateResponse(request, 'admin/shop_statistics.html', context)


def _extend_admin_urls(existing_get_urls):
    def get_urls():
        custom_urls = [
            path('statistics/', admin.site.admin_view(admin_statistics_view), name='shop_admin_statistics'),
        ]
        return custom_urls + existing_get_urls()
    return get_urls


admin.site.get_urls = _extend_admin_urls(admin.site.get_urls)


def _extend_admin_app_list(existing_get_app_list):
    def get_app_list(request, app_label=None):
        app_list = existing_get_app_list(request, app_label)

        for app in app_list:
            if app.get('app_label') != 'shop':
                continue

            models = app.setdefault('models', [])
            already_exists = any(model.get('object_name') == 'ShopStatistics' for model in models)
            if already_exists:
                break

            models.append({
                'name': 'Статистика магазину',
                'object_name': 'ShopStatistics',
                'admin_url': '/admin/statistics/',
                'add_url': None,
                'view_only': True,
                'perms': {'add': False, 'change': False, 'delete': False, 'view': True},
            })
            models.sort(key=lambda item: item.get('name', ''))
            break

        return app_list

    return get_app_list


admin.site.get_app_list = _extend_admin_app_list(admin.site.get_app_list)

admin.site.register(Category)


@admin.register(SiteVisit)
class SiteVisitAdmin(admin.ModelAdmin):
    list_display = ('visit_date', 'session_key', 'customer', 'created_at')
    list_filter = ('visit_date',)
    search_fields = ('session_key', 'customer__username', 'customer__email')
    readonly_fields = ('visit_date', 'session_key', 'customer', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

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