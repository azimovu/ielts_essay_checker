import requests
import hashlib
from uuid import uuid4 
from web_server import generate_auth_header 
import logging
from config import CLICK_MERCHANT_ID, CLICK_SERVICE_ID, CLICK_SECRET_KEY

CLICK_API_URL='https://api.click.uz/v2/merchant/'

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_invoice(amount, phone_number):
    """`
    Creates a Click.uz invoice with a unique merchant_trans_id and return URL.

    Args:
        amount (float): The invoice amount.
        phone_number (str): The phone number of the invoice recipient.

    Returns:
        dict: The JSON response from the Click.uz API.
    """

    merchant_trans_id = str(uuid4())  # Generate a unique ID

    auth_header = generate_auth_header()
    data = {
        "service_id": CLICK_SERVICE_ID,
        "amount": amount,
        "phone_number": phone_number,
        "merchant_trans_id": merchant_trans_id,
        "return_url": "http://www.uzielts.uz/click/complete" # Add the return URL
    }

    response = requests.post(
        "https://api.click.uz/v2/merchant/invoice/create",
        headers=auth_header,
        json=data,
    )
    return response.json()


def check_invoice_status(invoice_id):
    """Check the status of an invoice."""
    url = f"{CLICK_API_URL}/check-invoice/{invoice_id}"
    headers = {
        'Authorization': f"Bearer {CLICK_SECRET_KEY}"
    }

    try:
        logger.info(f"Checking status of invoice {invoice_id}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        status_data = response.json()
        logger.info(f"Invoice status: {status_data}")
        return status_data
    except requests.exceptions.RequestException as e:
        logger.error(f"Error checking invoice status: {e}")
        return None

def check_payment_status(payment_id):
    """Check the status of a payment."""
    url = f"{CLICK_API_URL}/check-payment/{payment_id}"
    headers = {
        'Authorization': f"Bearer {CLICK_SECRET_KEY}"
    }

    try:
        logger.info(f"Checking status of payment {payment_id}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        payment_data = response.json()
        logger.info(f"Payment status: {payment_data}")
        return payment_data
    except requests.exceptions.RequestException as e:
        logger.error(f"Error checking payment status: {e}")
        return None
