import requests
from django.conf import settings

def initialize_transaction(email, amount, callback_url, plan, user_id):
    url = f"{settings.PAYSTACK_BASE_URL}/transaction/initialize"
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    data = {
        "email": email,
        "amount": amount,  # already in kobo
        "callback_url": callback_url,
        "metadata": {
            "plan": plan,
            "user_id": user_id,
        },
    }
    response = requests.post(url, headers=headers, json=data)  # use json not data
    return response.json()

def verify_transaction(reference):
    url = f"{settings.PAYSTACK_BASE_URL}/transaction/verify/{reference}"
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    response = requests.get(url, headers=headers)
    return response.json()
