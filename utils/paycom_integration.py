import hashlib
import base64
from enum import IntEnum
import logging
from typing import Dict, Any, Optional
import aiohttp
from config import PAYCOM_MERCHANT_ID, PAYCOM_SECRET_KEY

logger = logging.getLogger(__name__)

class TransactionState(IntEnum):
    STATE_NEW = 1
    STATE_IN_PROGRESS = 2
    STATE_COMPLETED = 3
    STATE_CANCELLED = -1
    STATE_CANCELLED_AFTER_COMPLETE = -2

class PaycomError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

def verify_paycom_request(headers: Dict[str, str]) -> bool:
    """Verify the authenticity of incoming Paycom requests."""
    try:
        auth_header = headers.get('Authorization', '')
        if not auth_header.startswith('Basic '):
            raise PaycomError(-32504, "Authorization header must start with 'Basic'")
        
        encoded_auth = auth_header.split(' ')[1]
        decoded_auth = base64.b64decode(encoded_auth).decode('utf-8')
        merchant_id = decoded_auth.split(':')[0]
        
        if merchant_id != PAYCOM_MERCHANT_ID:
            raise PaycomError(-32504, 'Unauthorized merchant')
        
        expected_token = f"{PAYCOM_MERCHANT_ID}:{PAYCOM_SECRET_KEY}"
        expected_hash = base64.b64encode(expected_token.encode()).decode()
        
        return encoded_auth == expected_hash
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        return False

async def create_transaction(amount: int, order_id: str) -> Dict[str, Any]:
    """Create a new transaction in Paycom."""
    headers = {
        'X-Auth': f"{PAYCOM_MERCHANT_ID}:{PAYCOM_SECRET_KEY}",
        'Content-Type': 'application/json'
    }
    
    data = {
        "method": "CreateTransaction",
        "params": {
            "amount": amount * 100,  # Convert to tiyin
            "account": {
                "order_id": order_id
            }
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://checkout.paycom.uz/api',
                headers=headers,
                json=data
            ) as response:
                result = await response.json()
                logger.info(f"Create transaction response: {result}")
                return result
    except Exception as e:
        logger.error(f"Error creating transaction: {str(e)}")
        raise PaycomError(-31001, f"Error creating transaction: {str(e)}")

async def check_transaction(transaction_id: str) -> Dict[str, Any]:
    """Check transaction status in Paycom."""
    headers = {
        'X-Auth': f"{PAYCOM_MERCHANT_ID}:{PAYCOM_SECRET_KEY}",
        'Content-Type': 'application/json'
    }
    
    data = {
        "method": "CheckTransaction",
        "params": {
            "id": transaction_id
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://checkout.paycom.uz/api',
                headers=headers,
                json=data
            ) as response:
                result = await response.json()
                logger.info(f"Check transaction response: {result}")
                return result
    except Exception as e:
        logger.error(f"Error checking transaction: {str(e)}")
        raise PaycomError(-31003, f"Error checking transaction: {str(e)}")

def handle_paycom_response(response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Handle Paycom API response and standardize error handling."""
    if 'error' in response:
        error = response['error']
        logger.error(f"Paycom error: {error}")
        raise PaycomError(error.get('code', -31000), error.get('message', 'Unknown error'))
    return response.get('result')