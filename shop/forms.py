from django import forms
from .models import Order, Customer, Review, ReviewReply

PAYMENT_CHOICES = [
    ('online', 'Онлайн'),
    ('cod', 'Наложений платіж'),
]

DELIVERY_CHOICES = [
    ('np_branch', 'Відділення НП'),
    ('courier_kyiv', 'Курʼєр по Києву'),
]


def _validate_name_without_digits(value, field_label):
    normalized_value = (value or '').strip()
    if any(ch.isdigit() for ch in normalized_value):
        raise forms.ValidationError(f'{field_label} не може містити цифри')
    return normalized_value

class CheckoutForm(forms.ModelForm):
    delivery_method = forms.ChoiceField(
        choices=DELIVERY_CHOICES,
        label='Спосіб доставки',
        widget=forms.Select(attrs={
            'class': 'form-control',
            'data-delivery-method': 'true',
        }),
        required=True,
        error_messages={
            'required': 'Оберіть спосіб доставки',
        }
    )

    payment_method = forms.ChoiceField(
        choices=PAYMENT_CHOICES,
        label='Спосіб оплати',
        widget=forms.Select(attrs={
            'class': 'form-control',
        }),
        required=True,
        error_messages={
            'required': 'Оберіть спосіб оплати',
        }
    )

    class Meta:
        model = Order
        fields = [
            'first_name',
            'last_name',
            'email',
            'phone',
            'address',
            'city',
            'postal_code',
            'postal_branch',
            'delivery_method',
            'payment_method',
        ]
        labels = {
            'first_name': "Ім'я",
            'last_name': 'Прізвище',
            'email': 'Email адреса',
            'phone': 'Номер телефону',
            'address': 'Адреса',
            'city': 'Місто',
            'postal_code': 'Поштовий індекс',
            'postal_branch': 'Відділення НП',
            'delivery_method': 'Спосіб доставки',
            'payment_method': 'Спосіб оплати',
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'required': True, 'class': 'form-control', 'placeholder': 'Ім\'я'}),
            'last_name': forms.TextInput(attrs={'required': True, 'class': 'form-control', 'placeholder': 'Прізвище'}),
            'email': forms.EmailInput(attrs={'required': True, 'class': 'form-control', 'placeholder': 'Email адреса'}),
            'phone': forms.TextInput(attrs={'required': True, 'class': 'form-control', 'placeholder': 'Номер телефону'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Вулиця, будинок, квартира'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Місто'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Поштовий індекс'}),
            'postal_branch': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Вкажіть номер/назву відділення НП', 'data-postal-branch': 'true'}),
        }

    def clean_first_name(self):
        return _validate_name_without_digits(self.cleaned_data.get('first_name'), "Ім'я")

    def clean_last_name(self):
        return _validate_name_without_digits(self.cleaned_data.get('last_name'), 'Прізвище')

    def clean(self):
        cleaned_data = super().clean()
        delivery_method = cleaned_data.get('delivery_method')
        postal_branch = (cleaned_data.get('postal_branch') or '').strip()

        if delivery_method == 'np_branch' and not postal_branch:
            self.add_error('postal_branch', 'Вкажіть відділення Нової Пошти')

        if delivery_method != 'np_branch':
            cleaned_data['postal_branch'] = ''

        return cleaned_data


class RegistrationForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Пароль'
        })
    )
    password2 = forms.CharField(
        label='Підтвердіть пароль',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Підтвердіть пароль'
        })
    )

    class Meta:
        model = Customer
        fields = ('username', 'email', 'first_name', 'last_name')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ім\'я користувача'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email адреса'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ім\'я'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Прізвище'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError('Паролі не збігаються')
        
        return cleaned_data

    def save(self, commit=True):
        customer = super().save(commit=False)
        customer.set_password(self.cleaned_data['password1'])
        if commit:
            customer.save()
        return customer

    def clean_first_name(self):
        return _validate_name_without_digits(self.cleaned_data.get('first_name'), "Ім'я")

    def clean_last_name(self):
        return _validate_name_without_digits(self.cleaned_data.get('last_name'), 'Прізвище')


class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ім\'я користувача'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Пароль'
        })
    )

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ('first_name', 'last_name', 'email', 'phone', 'address', 'city', 'postal_code')
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ім\'я'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Прізвище'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email адреса'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Номер телефону'
            }),
            'address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Адреса'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Місто'
            }),
            'postal_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Поштовий індекс'
            }),
        }

    def clean_first_name(self):
        return _validate_name_without_digits(self.cleaned_data.get('first_name'), "Ім'я")

    def clean_last_name(self):
        return _validate_name_without_digits(self.cleaned_data.get('last_name'), 'Прізвище')


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'title', 'text']
        widgets = {
            'rating': forms.RadioSelect(choices=Review.RATING_CHOICES, attrs={
                'class': 'rating-input'
            }),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Заголовок відгуку',
                'maxlength': '200'
            }),
            'text': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Напишіть ваш відгук...',
                'rows': '5',
                'maxlength': '5000'
            }),
        }


class ReviewReplyForm(forms.ModelForm):
    class Meta:
        model = ReviewReply
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Напишіть відповідь...',
                'rows': '3',
                'maxlength': '2000'
            }),
        }