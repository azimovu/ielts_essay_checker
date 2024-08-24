import requests
import logging
from config import CLICK_MERCHANT_ID, CLICK_SERVICE_ID, CLICK_SECRET_KEY

CLICK_API_URL='https://api.click.uz/v2/merchant/'

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_invoice(amount, transaction_param):
    """Create an invoice using Click.uz."""
    url = f"{CLICK_API_URL}/create-invoice"
    data = {
        'service_id': CLICK_SERVICE_ID,
        'merchant_id': CLICK_MERCHANT_ID,
        'amount': amount,
        'transaction_param': transaction_param,
    }
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {CLICK_SECRET_KEY}"
    }

    try:
        logger.info(f"Creating invoice with data: {data}")
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        invoice_data = response.json()
        logger.info(f"Invoice created successfully: {invoice_data}")
        return invoice_data
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating invoice: {e}")
        return None

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
