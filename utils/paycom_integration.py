from typing import Dict, Any, Tuple
import hashlib
import time
import requests
from config import PAYCOM_MERCHANT_KEY, PAYCOM_TEST_URL, PAYCOM_PROD_URL
import logging
from database import (
    TransactionState, create_transaction, get_transaction_by_paycom_id,
    update_transaction_status, get_pending_transaction
)

logger = logging.getLogger(__name__)



class PaycomException(Exception):
    def __init__(self, error_code: int, error_message: str):
        self.error_code = error_code
        self.error_message = error_message
        super().__init__(self.error_message)

class PaycomIntegration:
    def __init__(self, is_test: bool = True):
        self.merchant_key = PAYCOM_MERCHANT_KEY
        self.base_url = PAYCOM_TEST_URL if is_test else PAYCOM_PROD_URL
        
    def _generate_auth_header(self) -> Dict[str, str]:
        auth_token = f"{self.merchant_key}".encode('utf-8')
        auth_header = f"Basic {auth_token.b64encode().decode('utf-8')}"
        return {
            "Authorization": auth_header,
            "Content-Type": "application/json"
        }
    
    async def create_invoice(self, amount: int, user_id: int, return_url: str) -> Tuple[str, str]:
        """Create a Paycom invoice for payment"""
        headers = self._generate_auth_header()
        
        # Calculate uses based on amount
        uses = self.calculate_uses(amount)
        
        payload = {
            "method": "paycom.merchant.create",
            "params": {
                "amount": amount,
                "account": {
                    "user_id": str(user_id)
                },
                "return_url": return_url
            },
            "id": int(time.time() * 1000)
        }
        
        try:
            response = requests.post(self.base_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if "error" in data:
                raise PaycomException(data["error"]["code"], data["error"]["message"])
            
            # Create transaction record in database
            create_transaction(
                user_id=user_id,
                paycom_transaction_id=data["result"]["invoice_id"],
                amount=amount,
                uses=uses
            )
                
            return data["result"]["invoice_id"], data["result"]["payment_url"]
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating Paycom invoice: {str(e)}")
            raise PaycomException(-1, "Failed to create invoice")
    
    def calculate_uses(self, amount_tiyin: int) -> int:
        """Calculate number of uses based on payment amount"""
        amount_uzs = amount_tiyin / 100
        if amount_uzs == 5000:
            return 5
        elif amount_uzs == 10000:
            return 10
        elif amount_uzs == 16000:
            return 20
        else:
            return int(amount_uzs / 1000)
    
    async def check_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """Check the status of a Paycom invoice"""
        headers = self._generate_auth_header()
        
        payload = {
            "method": "paycom.invoice.check",
            "params": {
                "invoice_id": invoice_id
            },
            "id": int(time.time() * 1000)
        }
        
        try:
            response = requests.post(self.base_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if "error" in data:
                raise PaycomException(data["error"]["code"], data["error"]["message"])
            
            # Update transaction status in database
            if data["result"]["state"] == 2:  # Paid
                update_transaction_status(
                    invoice_id,
                    TransactionState.PAID,
                    perform_time=int(time.time() * 1000)
                )
            elif data["result"]["state"] == -1:  # Cancelled
                update_transaction_status(
                    invoice_id,
                    TransactionState.CANCELLED,
                    cancel_time=int(time.time() * 1000)
                )
            elif data["result"]["state"] == -2:  # Failed
                update_transaction_status(
                    invoice_id,
                    TransactionState.FAILED,
                    cancel_time=int(time.time() * 1000)
                )
                
            return data["result"]
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error checking Paycom invoice: {str(e)}")
            raise PaycomException(-1, "Failed to check invoice")
            
    async def check_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """Check the status of a Paycom transaction"""
        headers = self._generate_auth_header()
        
        payload = {
            "method": "paycom.transaction.check",
            "params": {
                "id": transaction_id
            },
            "id": int(time.time() * 1000)
        }
        
        try:
            response = requests.post(self.base_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if "error" in data:
                raise PaycomException(data["error"]["code"], data["error"]["message"])
            
            # Update transaction status if needed
            transaction_state = data["result"].get("state", 0)
            if transaction_state == 2:  # Paid
                update_transaction_status(
                    transaction_id,
                    TransactionState.PAID,
                    perform_time=data["result"].get("perform_time")
                )
            
            return data["result"]
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error checking Paycom transaction: {str(e)}")
            raise PaycomException(-1, "Failed to check transaction")