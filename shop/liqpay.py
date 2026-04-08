"""
LiqPay payment integration helper.

Docs: https://www.liqpay.ua/en/documentation/api/aquiring/checkout/doc
"""
import base64
import hashlib
import json

LIQPAY_CHECKOUT_URL = 'https://www.liqpay.ua/api/3/checkout'


def _encode_params(params: dict) -> str:
    return base64.b64encode(json.dumps(params, ensure_ascii=False).encode('utf-8')).decode('utf-8')


def _make_signature(private_key: str, data: str) -> str:
    raw = (private_key + data + private_key).encode('utf-8')
    return base64.b64encode(hashlib.sha1(raw).digest()).decode('utf-8')


def build_checkout_form(public_key: str, private_key: str, order_id: int,
                        amount, description: str,
                        server_url: str, result_url: str,
                        sandbox: bool = True) -> dict:
    """
    Повертає словник із полями `data`, `signature` та `action_url`
    для побудови auto-submit form до LiqPay.
    """
    params = {
        'version': '3',
        'public_key': public_key,
        'action': 'pay',
        'amount': str(amount),
        'currency': 'UAH',
        'description': description,
        'order_id': str(order_id),
        'server_url': server_url,   # LiqPay викликає цей URL після оплати (server-to-server)
        'result_url': result_url,   # Перенаправляє юзера ПІСЛЯ оплати
        'language': 'uk',
    }
    if sandbox:
        params['sandbox'] = '1'

    data = _encode_params(params)
    signature = _make_signature(private_key, data)

    return {
        'data': data,
        'signature': signature,
        'action_url': LIQPAY_CHECKOUT_URL,
    }


def verify_callback(private_key: str, data: str, signature: str) -> bool:
    """Перевіряє підпис callback від LiqPay"""
    expected = _make_signature(private_key, data)
    return expected == signature


def decode_callback(data: str) -> dict:
    """Розкодовує base64 → dict з даними платежу"""
    return json.loads(base64.b64decode(data).decode('utf-8'))
