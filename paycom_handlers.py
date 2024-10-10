from flask import jsonify
import time
import base64
import logging
from typing import Dict, Any
from database import (
    TransactionState, create_transaction, get_transaction_by_paycom_id,
    update_transaction_status, get_user, add_purchased_uses
)

logger = logging.getLogger(__name__)

def handle_check_transaction_status(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle CheckTransaction request"""
    try:
        paycom_id = params.get('id')
        
        transaction = get_transaction_by_paycom_id(paycom_id)
        if not transaction:
            return {
                'error': {
                    'code': -31003,
                    'message': 'Transaction not found'
                }
            }
        
        result = {
            'result': {
                'create_time': transaction[7],    # create_time
                'perform_time': transaction[8],   # perform_time (will be 0 if not performed)
                'cancel_time': transaction[9],    # cancel_time (will be 0 if not cancelled)
                'transaction': str(transaction[0]),
                'state': transaction[3],          # transaction state
                'reason': transaction[10] if transaction[10] else None  # reason can be null
            }
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error in check transaction status: {str(e)}")
        return {
            'error': {
                'code': -31008,
                'message': str(e)
            }
        }

def verify_paycom_auth(auth_header: str, merchant_key: str) -> bool:
    """Verify Paycom request authentication"""
    if not auth_header or not auth_header.startswith('Basic '):
        return False
    
    try:
        decoded = base64.b64decode(auth_header[6:]).decode('utf-8')
        key = decoded.split(':')[1]
        return key == merchant_key
    except Exception as e:
        logger.error(f"Auth verification error: {str(e)}")
        return False

def handle_check_transaction(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle CheckPerformTransaction request"""
    try:
        account = params.get('account', {})
        user_id = int(account.get('user_id'))
        amount = params.get('amount')
        
        user = get_user(user_id)
        if not user:
            return {
                'error': {
                    'code': -31050,
                    'message': 'User not found'
                }
            }
        
        existing_transaction = get_transaction_by_paycom_id(params.get('id'))
        if existing_transaction:
            return {
                'error': {
                    'code': -31051,
                    'message': 'Transaction already exists'
                }
            }
        
        return {
            'result': {
                'allow': True
            }
        }
    except Exception as e:
        logger.error(f"Error in check transaction: {str(e)}")
        return {
            'error': {
                'code': -31008,
                'message': str(e)
            }
        }

def handle_create_transaction(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle CreateTransaction request"""
    try:
        account = params.get('account', {})
        user_id = int(account.get('user_id'))
        amount = params.get('amount')
        paycom_time = params.get('time')
        paycom_id = params.get('id')

        # First check if user exists
        user = get_user(user_id)
        if not user:
            return {
                'error': {
                    'code': -31050,
                    'message': 'User not found'
                }
            }
        
        existing_transaction = get_transaction_by_paycom_id(paycom_id)
        if existing_transaction:
            # Return existing transaction details with original create_time
            return {
                'result': {
                    'create_time': existing_transaction[7],  # Original create_time from DB
                    'transaction': str(existing_transaction[0]),
                    'state': existing_transaction[3]
                }
            }
        
        # Calculate uses based on amount (1000 tiyin = 1 UZS)
        uses = amount // 100000  # Convert tiyin to UZS and calculate uses
        
        transaction_id = create_transaction(
            user_id=user_id,
            paycom_transaction_id=paycom_id,
            amount=amount,
            uses=uses,
            create_time=paycom_time  # Store the original create_time
        )
        
        return {
            'result': {
                'create_time': paycom_time,
                'transaction': str(transaction_id),
                'state': 1  # Setting state to 1 for pending transaction
            }
        }
    except Exception as e:
        logger.error(f"Error in create transaction: {str(e)}")
        return {
            'error': {
                'code': -31001,
                'message': str(e)
            }
        }

def handle_perform_transaction(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle PerformTransaction request"""
    try:
        paycom_id = params.get('id')
        
        transaction = get_transaction_by_paycom_id(paycom_id)
        if not transaction:
            return {
                'error': {
                    'code': -31003,
                    'message': 'Transaction not found'
                }
            }
        
        if transaction[3] == 2:  # If already paid (state 2)
            return {
                'result': {
                    'transaction': str(transaction[0]),
                    'perform_time': transaction[8],
                    'state': 2
                }
            }
        
        current_time = int(time.time() * 1000)
        update_transaction_status(
            paycom_id,
            TransactionState.PAID,
            perform_time=current_time,
            cancel_time=0  # Explicitly set cancel_time to 0
        )
        
        # Add purchased uses only after successful payment
        add_purchased_uses(transaction[4], transaction[6])
        
        return {
            'result': {
                'transaction': str(transaction[0]),
                'perform_time': current_time,
                'state': 2  # State 2 indicates successful payment
            }
        }
    except Exception as e:
        logger.error(f"Error in perform transaction: {str(e)}")
        return {
            'error': {
                'code': -31008,
                'message': str(e)
            }
        }

def handle_cancel_transaction(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle CancelTransaction request"""
    try:
        paycom_id = params.get('id')
        reason = params.get('reason')
        
        transaction = get_transaction_by_paycom_id(paycom_id)
        if not transaction:
            return {
                'error': {
                    'code': -31003,
                    'message': 'Transaction not found'
                }
            }
        
        current_time = int(time.time() * 1000)
        
        update_transaction_status(
            paycom_id,
            TransactionState.CANCELLED,
            perform_time=0,  # Set perform_time to 0 when cancelling
            cancel_time=current_time,
            reason=reason  # reason can be null
        )
        
        return {
            'result': {
                'transaction': str(transaction[0]),
                'cancel_time': current_time,
                'state': -1  # State -1 indicates cancelled transaction
            }
        }
    except Exception as e:
        logger.error(f"Error in cancel transaction: {str(e)}")
        return {
            'error': {
                'code': -31008,
                'message': str(e)
            }
        }