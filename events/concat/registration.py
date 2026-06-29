from django.conf import settings

from .api import get_json
from .oauth import get_service_token


def get_registration(user_id, token=None):
    if token is None:
        token = get_service_token()
    return get_json(f'{settings.CONCAT_API_V0_BASE}/users/{user_id}/registration', bearer=token)


def registration_product_ids(registration):
    product_ids = set()

    def add_if_int(value):
        try:
            product_ids.add(int(value))
        except (TypeError, ValueError):
            return

    if not isinstance(registration, dict):
        return product_ids

    add_if_int(registration.get('productId'))

    for value in registration.get('productIds') or []:
        add_if_int(value)

    for product in registration.get('products') or []:
        if isinstance(product, dict):
            add_if_int(product.get('id'))
            add_if_int(product.get('productId'))

    return product_ids
