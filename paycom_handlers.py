from flask import jsonify
import time
import logging
import base64
from typing import Dict, Any
from database import (
    TransactionState, create_transaction, get_transaction_by_paycom_id,
    update_transaction_status, get_user, add_purchased_uses, get_transactions_in_range
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
        
        # Assuming transaction tuple structure:
        # (id, paycom_id, user_id, state, amount, uses, create_time, perform_time, cancel_time, reason)
        result = {
            'result': {
                'create_time': int(transaction[6]),  # create_time
                'perform_time': int(transaction[7]) if transaction[7] else 0,  # perform_time
                'cancel_time': int(transaction[8]) if transaction[8] else 0,   # cancel_time
                'transaction': str(transaction[0]),   # transaction id
                'state': int(transaction[2]),        # transaction state
                'reason': transaction[9] if transaction[9] else None  # reason
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
        create_time = params.get('time')  # This is the time from the request
        paycom_id = params.get('id')

        if not all([user_id, amount, create_time, paycom_id]):
            return {
                'error': {
                    'code': -32600,
                    'message': 'Invalid request parameters'
                }
            }

        # First check if user exists
        user = get_user(user_id)
        if not user:
            return {
                'error': {
                    'code': -31050,
                    'message': 'User not found'
                }
            }
        
        # Check for existing transaction
        existing_transaction = get_transaction_by_paycom_id(paycom_id)
        if existing_transaction:
            # Return existing transaction details with original create_time
            return {
                'result': {
                    'create_time': existing_transaction[6],  # Index of create_time in the tuple
                    'transaction': str(existing_transaction[0]),
                    'state': existing_transaction[2]  # Index of paycom_state in the tuple
                }
            }
        
        # Calculate uses based on amount (1000 tiyin = 1 UZS)
        uses = amount // 100000  # Convert tiyin to UZS and calculate uses
        
        # Create new transaction
        transaction_id = create_transaction(
            user_id=user_id,
            paycom_transaction_id=paycom_id,
            amount=amount,
            uses=uses,
            create_time=create_time
        )
        
        return {
            'result': {
                'create_time': create_time,
                'transaction': str(transaction_id),
                'state': TransactionState.CREATED.value
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


def handle_perform_transaction(params):
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
        
        # If already paid (state 2), return the same response
        if transaction[2] == TransactionState.PAID.value:
            return {
                'result': {
                    'transaction': str(transaction[0]),
                    'perform_time': int(transaction[7]),
                    'state': TransactionState.PAID.value
                }
            }
        
        # Only proceed if transaction is in CREATED state
        if transaction[2] != TransactionState.CREATED.value:
            return {
                'error': {
                    'code': -31008,
                    'message': 'Transaction state is invalid'
                }
            }
        
        current_time = int(time.time() * 1000)
        update_transaction_status(
            paycom_id,
            TransactionState.PAID,
            perform_time=current_time,
            cancel_time=0  # Explicitly set cancel_time to 0
        )
        
        return {
            'result': {
                'transaction': str(transaction[0]),
                'perform_time': current_time,
                'state': TransactionState.PAID.value
            }
        }
    except Exception as e:
        return {
            'error': {
                'code': -31008,
                'message': str(e)
            }
        }

def handle_cancel_transaction(params):
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
        
        # Check if the transaction is already in a final state
        if transaction[2] in [TransactionState.PAID.value]:
            return {
                'error': {
                    'code': -31007,
                    'message': 'Unable to cancel transaction in final state'
                }
            }
        
        current_time = int(time.time() * 1000)
        
        # Only update cancel_time if it's not already set
        cancel_time = transaction[8] or current_time
        
        update_transaction_status(
            paycom_id,
            TransactionState.CANCELLED,
            perform_time=0,  # Set perform_time to 0 when cancelling
            cancel_time=cancel_time,
            reason=reason
        )
        
        return {
            'result': {
                'transaction': str(transaction[0]),
                'cancel_time': cancel_time,
                'state': TransactionState.CANCELLED.value
            }
        }
    except Exception as e:
        return {
            'error': {
                'code': -31008,
                'message': str(e)
            }
        }
    

def handle_get_statement(params):
    try:
        from_date = params.get('from')
        to_date = params.get('to')
        
        if not from_date or not to_date:
            return {
                'error': {
                    'code': -32504,
                    'message': 'From or to date not provided'
                }
            }
        
        transactions = get_transactions_in_range(from_date, to_date)
        
        statements = []
        for transaction in transactions:
            statement = {
                'id': transaction[1],  # paycom_transaction_id
                'time': transaction[6],  # create_time
                'amount': transaction[4],
                'account': {
                    'user_id': transaction[3]
                },
                'create_time': transaction[6],
                'perform_time': transaction[7] or 0,
                'cancel_time': transaction[8] or 0,
                'transaction': str(transaction[0]),
                'state': transaction[2],
                'reason': transaction[9] if transaction[9] is not None else None,
                'receivers': []
            }
            statements.append(statement)
        
        return {
            'result': {
                'transactions': statements
            }
        }
    except Exception as e:
        return {
            'error': {
                'code': -31008,
                'message': str(e)
            }
        }
