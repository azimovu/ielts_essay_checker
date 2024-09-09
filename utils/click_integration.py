import aiohttp
import hashlib
import time
from uuid import uuid4
import logging
from config import CLICK_MERCHANT_ID, CLICK_SERVICE_ID, CLICK_SECRET_KEY

CLICK_API_URL = 'https://api.click.uz/v2/merchant/'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def generate_auth_header():
    timestamp = str(int(time.time()))
    digest = hashlib.sha1((timestamp + CLICK_SECRET_KEY).encode()).hexdigest()
    auth_header = f'{CLICK_MERCHANT_ID}:{digest}:{timestamp}'
    return {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Auth': auth_header
    }

async def create_invoice(amount, phone_number):
    merchant_trans_id = str(uuid4())
    auth_header = await generate_auth_header()
    data = {
        "service_id": CLICK_SERVICE_ID,
        "amount": amount,
        "phone_number": phone_number,
        "merchant_trans_id": merchant_trans_id,
        "return_url": "http://www.uzielts.uz/click/complete"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{CLICK_API_URL}invoice/create", headers=auth_header, json=data) as response:
            return await response.json(), merchant_trans_id

async def check_invoice_status(invoice_id):
    auth_header = await generate_auth_header()
    url = f"{CLICK_API_URL}invoice/status/{CLICK_SERVICE_ID}/{invoice_id}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=auth_header) as response:
            return await response.json()

async def check_payment_status(payment_id):
    auth_header = await generate_auth_header()
    url = f"{CLICK_API_URL}payment/status/{CLICK_SERVICE_ID}/{payment_id}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=auth_header) as response:
            return await response.json()