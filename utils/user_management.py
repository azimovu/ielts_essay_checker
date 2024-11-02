# utils/user_management.py
from typing import Dict, Any, Tuple
import hashlib
import time
import requests
import logging
from database import (
    TransactionState, create_transaction, get_transaction_by_click_id,
    update_transaction_status, get_pending_transaction,
    add_user, get_user, update_phone_number,
    get_free_uses_left, get_purchased_uses,
    decrement_free_uses, decrement_purchased_uses
)
from utils.click_integration import ClickIntegration, ClickException

logger = logging.getLogger(__name__)

class UserManager:
    def __init__(self):
        self.click = ClickIntegration()

    async def initialize_user(self, user_id: int, phone_number: str = None):
        """Initialize a new user in the system"""
        add_user(user_id)
        if phone_number:
            update_phone_number(user_id, phone_number)

    async def check_user_access(self, user_id: int) -> Tuple[bool, str]:
        """Check if user has available uses (free or purchased)"""
        free_uses = get_free_uses_left(user_id)
        purchased_uses = get_purchased_uses(user_id)

        if free_uses > 0:
            return True, "free"
        elif purchased_uses > 0:
            return True, "purchased"
        else:
            return False, "none"

    async def use_service(self, user_id: int) -> bool:
        """Process a service usage for the user"""
        has_access, access_type = await self.check_user_access(user_id)
        
        if not has_access:
            return False

        if access_type == "free":
            decrement_free_uses(user_id)
        else:  # purchased
            decrement_purchased_uses(user_id)
        
        return True

    async def initiate_payment(self, user_id: int, amount: float, phone_number: str) -> Dict[str, Any]:
        """Initiate a payment for the user"""
        try:
            invoice_id, invoice_data = await self.click.create_invoice(
                amount=amount,
                user_id=user_id,
                phone_number=phone_number
            )
            
            return {
                "success": True,
                "invoice_id": invoice_id,
                "data": invoice_data
            }
        except ClickException as e:
            logger.error(f"Payment initiation error for user {user_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error during payment initiation: {str(e)}")
            return {
                "success": False,
                "error": "An unexpected error occurred"
            }

    async def check_payment_status(self, invoice_id: str) -> Dict[str, Any]:
        """Check the status of a payment"""
        try:
            status_data = await self.click.check_invoice(invoice_id)
            return {
                "success": True,
                "status": status_data
            }
        except ClickException as e:
            logger.error(f"Payment status check error for invoice {invoice_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error during payment status check: {str(e)}")
            return {
                "success": False,
                "error": "An unexpected error occurred"
            }

    def get_payment_packages(self) -> list:
        """Return available payment packages"""
        return [
            {"uses": 5, "amount": 5000, "description": "5 uses package"},
            {"uses": 10, "amount": 10000, "description": "10 uses package"},
            {"uses": 20, "amount": 16000, "description": "20 uses package (20% discount)"}
        ]

    async def get_user_status(self, user_id: int) -> Dict[str, Any]:
        """Get user's current status including remaining uses"""
        user = get_user(user_id)
        if not user:
            return None

        pending_transaction = get_pending_transaction(user_id)
        
        return {
            "user_id": user_id,
            "free_uses_left": get_free_uses_left(user_id),
            "purchased_uses": get_purchased_uses(user_id),
            "has_pending_payment": pending_transaction is not None,
            "pending_transaction": pending_transaction
        }