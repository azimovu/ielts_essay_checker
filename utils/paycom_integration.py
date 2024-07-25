import requests
from typing import Dict, Any

PAYCOM_TEST_URL = "https://checkout.test.paycom.uz/api"
PAYCOM_TOKEN = "371317599:TEST:1721717956046"

def create_test_invoice(amount: int, order_id: str) -> Dict[str, Any]:
    """
    Create a test invoice using the Paycom API.
    
    :param amount: Amount in tiyins (100 tiyin = 1 UZS)
    :param order_id: Unique order identifier
    :return: Dictionary containing the response from Paycom
    """
    headers = {
        "X-Auth": PAYCOM_TOKEN,
        "Content-Type": "application/json"
    }
    
    payload = {
        "method": "paycom.merchant.create",
        "params": {
            "amount": amount,
            "account": {
                "order_id": order_id
            }
        }
    }
    
    response = requests.post(PAYCOM_TEST_URL, json=payload, headers=headers)
    return response.json()

def check_transaction(transaction_id: str) -> Dict[str, Any]:
    """
    Check the status of a transaction using the Paycom API.
    
    :param transaction_id: The ID of the transaction to check
    :return: Dictionary containing the response from Paycom
    """
    headers = {
        "X-Auth": PAYCOM_TOKEN,
        "Content-Type": "application/json"
    }
    
    payload = {
        "method": "paycom.transaction.check",
        "params": {
            "id": transaction_id
        }
    }
    
    response = requests.post(PAYCOM_TEST_URL, json=payload, headers=headers)
    return response.json()