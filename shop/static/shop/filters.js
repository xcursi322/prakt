// === MODERN SPORT SHOP JAVASCRIPT ===

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all features
    initializeFilters();
    initializeAnimations();
    initializeCartFeatures();
    initializeFormValidation();
});

// === FILTER FUNCTIONALITY ===
function initializeFilters() {
    const categoryFilter = document.getElementById('categoryFilter');
    const sortFilter = document.getElementById('sortFilter');
    const searchInput = document.getElementById('searchInput');

    if (categoryFilter) {
        categoryFilter.addEventListener('change', applyFilters);
    }

    if (sortFilter) {
        sortFilter.addEventListener('change', applyFilters);
    }

    if (searchInput) {
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                applyFilters();
            }
        });

        searchInput.addEventListener('change', applyFilters);
    }
}

function applyFilters() {
    const categoryFilter = document.getElementById('categoryFilter');
    const sortFilter = document.getElementById('sortFilter');
    const searchInput = document.getElementById('searchInput');
    const productsGrid = document.getElementById('productsGrid');
    const catalogHero = document.getElementById('catalogHero');
    const categoryId = categoryFilter ? categoryFilter.value : '';
    const sortValue = sortFilter ? sortFilter.value : '';
    const searchValue = searchInput ? searchInput.value.trim() : '';
    
    let url = window.location.pathname;
    const params = new URLSearchParams();

    if (categoryId) params.append('category', categoryId);
    if (sortValue) params.append('sort', sortValue);
    if (searchValue) params.append('q', searchValue);

    if (params.toString()) {
        url += '?' + params.toString();
    }

    if (!productsGrid) {
        window.location.href = url;
        return;
    }

    productsGrid.style.opacity = '0.55';

    fetch(url, {
        method: 'GET',
        credentials: 'same-origin',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
        },
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('catalog_filters_failed');
        }
        return response.json();
    })
    .then(data => {
        if (!data || !data.success || typeof data.products_html !== 'string') {
            throw new Error('catalog_filters_invalid_payload');
        }

        productsGrid.innerHTML = data.products_html;
        if (catalogHero && typeof data.hero_html === 'string') {
            catalogHero.innerHTML = data.hero_html;
        }
        productsGrid.style.opacity = '1';
        window.history.pushState({}, '', url);
    })
    .catch(() => {
        productsGrid.style.opacity = '1';
        window.location.href = url;
    });
}

// === ANIMATIONS ===
function initializeAnimations() {
    // Observe elements for fade-in animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('fade-in-up');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Observe product cards
    document.querySelectorAll('.product-card').forEach(card => {
        observer.observe(card);
    });

    // Observe form sections
    document.querySelectorAll('.form-group, .checkout-form').forEach(element => {
        observer.observe(element);
    });

    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            if (href !== '#') {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }
        });
    });
}

// === CART FEATURES ===
function initializeCartFeatures() {
    // Delegate add-to-cart clicks (in case buttons are re-rendered)
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-add-to-cart-url]');
        if (btn) {
            handleAddToCart.call(btn, e);
            return;
        }

        const cartActionBtn = e.target.closest('[data-cart-action]');
        if (cartActionBtn) {
            handleCartAction.call(cartActionBtn, e);
        }
    });
}

function handleAddToCart(e) {
    e.preventDefault();
    const addUrl = this.dataset.addToCartUrl;
    if (!addUrl) {
        showNotification('Не вдалося додати товар до кошика', 'error');
        return;
    }
    // Для каталога завжди quantity = 1
    fetch(addUrl, {
        method: 'GET',
        credentials: 'same-origin',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
        },
    })
    .then(async response => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok || data.success === false) {
            throw data;
        }
        return data;
    })
    .then(data => {
        if (!data) return;
        // Успішно додано
        showNotification(data.message || 'Товар додано до кошика!', 'success');
        // Оновити лічильник кошика (якщо є)
        const cartCount = document.querySelector('[data-cart-count]');
        if (cartCount && typeof data.cart_count !== 'undefined') {
            cartCount.textContent = data.cart_count;
        }
        // Анімація іконки кошика
        const cartIcon = document.querySelector('[data-cart-icon]');
        if (cartIcon) {
            cartIcon.style.animation = 'pulse-glow 0.6s ease';
            setTimeout(() => {
                cartIcon.style.animation = '';
            }, 600);
        }
    })
    .catch((errorData) => {
        if (errorData && errorData.message) {
            showNotification(errorData.message, 'error');
            return;
        }
        // Fallback: navigate to add URL to ensure item is added
        window.location.href = addUrl;
    });
}

function handleCartAction(e) {
    e.preventDefault();

    const actionType = this.dataset.cartAction;
    const actionUrl = this.getAttribute('href');
    if (!actionUrl) {
        return;
    }

    if (actionType === 'remove' && !window.confirm('Видалити товар з кошика?')) {
        return;
    }

    const cartItem = this.closest('[data-cart-item]');
    setCartActionsLoading(cartItem, true);

    fetch(actionUrl, {
        method: 'GET',
        credentials: 'same-origin',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
        },
    })
    .then(async response => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok || data.success === false) {
            throw data;
        }
        return data;
    })
    .then(data => {
        if (!data || typeof data.product_id === 'undefined') {
            setCartActionsLoading(cartItem, false);
            return;
        }

        applyCartUpdate(data);
        if (!data.removed) {
            setCartActionsLoading(cartItem, false);
        }
    })
    .catch((errorData) => {
        setCartActionsLoading(cartItem, false);
        if (errorData && errorData.message) {
            showNotification(errorData.message, 'error');
            return;
        }
        window.location.href = actionUrl;
    });
}

function setCartActionsLoading(cartItem, isLoading) {
    if (!cartItem) {
        return;
    }

    cartItem.querySelectorAll('[data-cart-action]').forEach(actionBtn => {
        if (isLoading) {
            actionBtn.classList.add('is-loading');
            actionBtn.setAttribute('aria-disabled', 'true');
            actionBtn.style.pointerEvents = 'none';
        } else {
            actionBtn.classList.remove('is-loading');
            actionBtn.removeAttribute('aria-disabled');
            actionBtn.style.pointerEvents = '';
        }
    });
}

function applyCartUpdate(data) {
    const productId = String(data.product_id);
    const cartItem = document.querySelector(`[data-cart-item][data-product-id="${productId}"]`);

    if (cartItem) {
        if (data.removed) {
            cartItem.style.opacity = '0';
            cartItem.style.transform = 'translateX(20px)';
            setTimeout(() => {
                cartItem.remove();
                toggleCartEmptyState(Boolean(data.empty));
            }, 220);
        } else {
            cartItem.setAttribute('data-quantity', String(data.quantity));
            cartItem.querySelectorAll('[data-item-qty]').forEach(el => {
                el.textContent = String(data.quantity);
            });

            const subtotalElement = cartItem.querySelector('[data-item-subtotal]');
            if (subtotalElement) {
                subtotalElement.textContent = formatHryvnia(data.subtotal);
            }
        }
    };

    const summaryRow = document.querySelector(`[data-summary-row][data-product-id="${productId}"]`);
    if (summaryRow) {
        if (data.removed) {
            summaryRow.remove();
        } else {
            const summaryQty = summaryRow.querySelector('[data-summary-qty]');
            const summarySubtotal = summaryRow.querySelector('[data-summary-subtotal]');
            if (summaryQty) {
                summaryQty.textContent = String(data.quantity);
            }
            if (summarySubtotal) {
                summarySubtotal.textContent = formatHryvnia(data.subtotal);
            }
        }
    }

    document.querySelectorAll('[data-cart-total-value]').forEach(el => {
        el.textContent = formatHryvnia(data.total);
    });

    const cartCount = document.querySelector('[data-cart-count]');
    if (cartCount && typeof data.cart_count !== 'undefined') {
        cartCount.textContent = String(data.cart_count);
    }

    toggleCartEmptyState(Boolean(data.empty));
}

function toggleCartEmptyState(isEmpty) {
    const cartContent = document.querySelector('[data-cart-content]');
    const cartEmpty = document.querySelector('[data-cart-empty]');

    if (!cartContent || !cartEmpty) {
        return;
    }

    if (isEmpty) {
        cartContent.classList.add('hidden');
        cartEmpty.classList.remove('hidden');
    } else {
        cartContent.classList.remove('hidden');
        cartEmpty.classList.add('hidden');
    }
}

function formatHryvnia(value) {
    const numericValue = Number(value) || 0;
    return `${numericValue.toLocaleString('uk-UA')} ₴`;
}

// === FORM VALIDATION ===
function initializeFormValidation() {
    const forms = document.querySelectorAll('[data-validate]');
    
    forms.forEach(form => {
        form.addEventListener('submit', validateForm);
        
        // Real-time validation
        form.querySelectorAll('input, select, textarea').forEach(field => {
            field.addEventListener('blur', validateField);
            field.addEventListener('change', validateField);
        });
    });
}

function validateForm(e) {
    const form = e.target;
    let isValid = true;

    form.querySelectorAll('input, select, textarea').forEach(field => {
        if (!validateField.call(field)) {
            isValid = false;
        }
    });

    if (!isValid) {
        e.preventDefault();
        showNotification('Будь ласка, заповніть усі поля правильно', 'error');
    }

    return isValid;
}

function validateField() {
    const field = this;
    const value = field.value.trim();
    const fieldName = field.name;
    let isValid = true;
    let errorMessage = '';

    // Remove previous error styling
    field.classList.remove('field-error');
    const existingError = field.parentElement.querySelector('.form-error');
    if (existingError) {
        existingError.remove();
    }
    const existingSuccess = field.parentElement.querySelector('.form-success');
    if (existingSuccess) {
        existingSuccess.remove();
    }

    // Validation rules
    if (field.hasAttribute('required') && !value) {
        isValid = false;
        errorMessage = 'Це поле обов\'язкове';
    } else if (field.type === 'email' && value && !isValidEmail(value)) {
        isValid = false;
        errorMessage = 'Введіть коректну електронну адресу';
    } else if (field.type === 'tel' && value && !isValidPhone(value)) {
        isValid = false;
        errorMessage = 'Введіть коректний номер телефону';
    } else if (fieldName === 'username' && value && value.length < 3) {
        isValid = false;
        errorMessage = 'Ім\'я користувача повинно мати мінімум 3 символи';
    } else if (fieldName === 'password' && value && value.length < 6) {
        isValid = false;
        errorMessage = 'Пароль повинен мати мінімум 6 символів';
    }

    // Show error if invalid
    if (!isValid) {
        field.classList.add('field-error');
        const errorEl = document.createElement('div');
        errorEl.className = 'form-error';
        errorEl.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${errorMessage}`;
        field.parentElement.appendChild(errorEl);
    }

    return isValid;
}

function isValidEmail(email) {
    const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return regex.test(email);
}

function isValidPhone(phone) {
    const regex = /^\+?[\d\s\-\(\)]{10,}$/;
    return regex.test(phone);
}

// === NOTIFICATIONS ===
function showNotification(message, type = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const normalizedType = ['success', 'error', 'info'].includes(type) ? type : 'info';
    const messageKey = `${normalizedType}:${String(message).trim()}`;

    const existing = container.querySelector(`[data-message-key="${CSS.escape(messageKey)}"]`);
    if (existing) {
        existing.remove();
    }

    const notification = document.createElement('div');
    notification.className = `toast-notification toast-${normalizedType}`;
    notification.dataset.messageKey = messageKey;

    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        info: 'fa-info-circle'
    };

    notification.innerHTML = `
        <i class="fas ${icons[normalizedType]} toast-icon"></i>
        <span class="toast-message">${message}</span>
        <button type="button" class="toast-close" aria-label="Close notification">×</button>
        <span class="toast-progress"></span>
    `;

    container.prepend(notification);

    const closeToast = () => {
        notification.classList.add('is-hiding');
        setTimeout(() => notification.remove(), 220);
    };

    const closeBtn = notification.querySelector('.toast-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeToast);
    }

    setTimeout(closeToast, 3800);
}

// === DROPDOWN MENU ===
function setupDropdowns() {
    document.querySelectorAll('[data-dropdown-toggle]').forEach(toggle => {
        const menu = toggle.nextElementSibling;
        if (menu && menu.hasAttribute('data-dropdown-menu')) {
            toggle.addEventListener('click', (e) => {
                e.preventDefault();
                menu.classList.toggle('show');
            });

            document.addEventListener('click', (e) => {
                if (!e.target.closest('[data-dropdown-toggle]') && !e.target.closest('[data-dropdown-menu]')) {
                    menu.classList.remove('show');
                }
            });
        }
    });
}

// Initialize on load
document.addEventListener('DOMContentLoaded', setupDropdowns);

// === UTILITY FUNCTIONS ===
function debounce(func, delay) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), delay);
    };
}

function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}
