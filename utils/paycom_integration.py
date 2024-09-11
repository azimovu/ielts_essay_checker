import hashlib
import json
import aiohttp
from config import PAYCOM_MERCHANT_ID, PAYCOM_SECRET_KEY

PAYCOM_API_URL = 'https://checkout.paycom.uz'

async def generate_auth_header():
    auth_token = f"{PAYCOM_MERCHANT_ID}:{PAYCOM_SECRET_KEY}"
    encoded_token = hashlib.md5(auth_token.encode()).hexdigest()
    return {
        'X-Auth': encoded_token,
        'Content-Type': 'application/json'
    }

async def create_transaction(amount, order_id):
    auth_header = await generate_auth_header()
    data = {
        "method": "create_transaction",
        "params": {
            "amount": amount * 100,  # Convert to tiyin
            "account": {
                "order_id": order_id
            }
        }
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(PAYCOM_API_URL, headers=auth_header, json=data) as response:
                response_data = await response.json()
                print(f"Transaction Response: {response_data}")  # Debugging log
                return response_data
    except Exception as e:
        print(f"Error creating transaction: {e}")  # Error log
        return {"error": str(e)}

async def check_transaction(transaction_id):
    auth_header = await generate_auth_header()
    data = {
        "method": "check_transaction",
        "params": {
            "id": transaction_id
        }
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(PAYCOM_API_URL, headers=auth_header, json=data) as response:
            return await response.json()

async def cancel_transaction(transaction_id, reason):
    auth_header = await generate_auth_header()
    data = {
        "method": "cancel_transaction",
        "params": {
            "id": transaction_id,
            "reason": reason
        }
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(PAYCOM_API_URL, headers=auth_header, json=data) as response:
            return await response.json()
