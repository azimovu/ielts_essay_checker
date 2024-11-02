# utils/click_integration.py
import hashlib
import time
import requests
from typing import Dict, Any, Tuple
import logging
from config import (
    CLICK_MERCHANT_ID, 
    CLICK_SERVICE_ID,
    CLICK_MERCHANT_USER_ID,
    CLICK_SECRET_KEY
)
from database import (
    TransactionState, 
    create_transaction, 
    get_transaction_by_click_id,
    update_transaction_status
)

logger = logging.getLogger(__name__)

class ClickException(Exception):
    def __init__(self, error_code: int, error_message: str):
        self.error_code = error_code
        self.error_message = error_message
        super().__init__(self.error_message)

class ClickIntegration:
    def __init__(self, is_test: bool = True):
        self.merchant_id = CLICK_MERCHANT_ID
        self.service_id = CLICK_SERVICE_ID
        self.merchant_user_id = CLICK_MERCHANT_USER_ID
        self.secret_key = CLICK_SECRET_KEY
        self.base_url = "https://api.click.uz/v2/merchant/"

    def _generate_auth_header(self) -> Dict[str, str]:
        timestamp = str(int(time.time()))
        digest = hashlib.sha1(
            (timestamp + self.secret_key).encode('utf-8')
        ).hexdigest()
        
        auth_header = f"{self.merchant_user_id}:{digest}:{timestamp}"
        
        return {
            "Auth": auth_header,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def calculate_uses(self, amount_uzs: float) -> int:
        """Calculate number of uses based on payment amount"""
        if amount_uzs == 5000:
            return 5
        elif amount_uzs == 10000:
            return 10
        elif amount_uzs == 16000:
            return 20
        else:
            return int(amount_uzs / 1000)

    async def create_invoice(self, amount: float, user_id: int, phone_number: str) -> Tuple[str, Dict]:
        """Create a Click invoice for payment"""
        headers = self._generate_auth_header()
        
        merchant_trans_id = f"order_{user_id}_{int(time.time())}"
        
        payload = {
            "service_id": self.service_id,
            "amount": amount,
            "phone_number": phone_number,
            "merchant_trans_id": merchant_trans_id
        }

        try:
            response = requests.post(
                f"{self.base_url}invoice/create",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            data = response.json()

            if data.get("error_code") != 0:
                raise ClickException(
                    data["error_code"], 
                    data.get("error_note", "Unknown error")
                )

            # Add service_id and merchant_id from instance variables
            data.update({
                'service_id': self.service_id,
                'merchant_id': self.merchant_id,
                'merchant_trans_id': merchant_trans_id
            })

            # Create transaction record
            uses = self.calculate_uses(amount)
            create_transaction(
                user_id=user_id,
                click_invoice_id=data["invoice_id"],
                amount=int(amount),
                uses=uses,
                create_time=int(time.time() * 1000),
                merchant_trans_id=merchant_trans_id
            )

            return str(data["invoice_id"]), data

        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating Click invoice: {str(e)}")
            raise ClickException(-1, "Failed to create invoice")

    async def check_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """Check Click invoice status"""
        headers = self._generate_auth_header()

        try:
            response = requests.get(
                f"{self.base_url}invoice/status/{self.service_id}/{invoice_id}",
                headers=headers
            )
            response.raise_for_status()
            data = response.json()

            logger.info(f"Click invoice status response: {data}")  # Add logging

            if data.get("error_code") != 0:
                return {
                    "error_code": data.get("error_code", -1),
                    "error_note": data.get("error_note", "Unknown error"),
                    "invoice_status": None,
                    "payment_id": None
                }

            # Ensure we have an invoice status
            invoice_status = data.get("invoice_status")
            if invoice_status is None:
                return {
                    "error_code": -1,
                    "error_note": "Invoice status not found in response",
                    "invoice_status": None,
                    "payment_id": None
                }

            return {
                "error_code": 0,
                "error_note": "",
                "invoice_status": invoice_status,
                "payment_id": data.get("payment_id")
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Error checking Click invoice: {str(e)}")
            return {
                "error_code": -1,
                "error_note": f"Failed to check invoice: {str(e)}",
                "invoice_status": None,
                "payment_id": None
            }