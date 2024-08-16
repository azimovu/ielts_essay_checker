import hashlib
import time
import requests
from config import CLICK_MERCHANT_ID, CLICK_SERVICE_ID, CLICK_SECRET_KEY, CLICK_MERCHANT_USER_ID

BASE_URL = "https://api.click.uz/v2/merchant/"

def generate_auth_header():
    timestamp = str(int(time.time()))
    digest = hashlib.sha1((timestamp + CLICK_SECRET_KEY).encode()).hexdigest()
    return f"{CLICK_MERCHANT_USER_ID}:{digest}:{timestamp}"

def create_invoice(amount, phone_number, merchant_trans_id):
    url = BASE_URL + "invoice/create"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Auth": generate_auth_header()
    }
    payload = {
        "service_id": CLICK_SERVICE_ID,
        "amount": amount,
        "phone_number": phone_number,
        "merchant_trans_id": merchant_trans_id
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()

def check_invoice_status(invoice_id):
    url = f"{BASE_URL}invoice/status/{CLICK_SERVICE_ID}/{invoice_id}"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Auth": generate_auth_header()
    }
    response = requests.get(url, headers=headers)
    return response.json()

def check_payment_status(payment_id):
    url = f"{BASE_URL}payment/status/{CLICK_SERVICE_ID}/{payment_id}"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Auth": generate_auth_header()
    }
    response = requests.get(url, headers=headers)
    return response.json()