from flask import Flask, request, jsonify
from config import (
    CLICK_MERCHANT_ID, 
    CLICK_SERVICE_ID, 
    CLICK_SECRET_KEY,
    CLICK_MERCHANT_USER_ID
)
import time
import hashlib
import logging
from logging.handlers import RotatingFileHandler
from waitress import serve
from database import (
    add_purchased_uses, 
    get_user,
    get_transaction_by_click_id,
    update_transaction_status,
    TransactionState
)
from utils.click_integration import ClickIntegration

app = Flask(__name__)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = RotatingFileHandler('flask_app.log', maxBytes=100000, backupCount=3)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def verify_click_signature(data: dict, signature: str) -> bool:
    """Verify Click request signature"""
    click_trans_id = str(data.get('click_trans_id', ''))
    service_id = str(data.get('service_id', ''))
    click_paydoc_id = str(data.get('click_paydoc_id', ''))
    merchant_trans_id = str(data.get('merchant_trans_id', ''))
    amount = str(data.get('amount', ''))
    action = str(data.get('action', ''))
    sign_time = str(data.get('sign_time', ''))

    sign_string = f"{click_trans_id}{service_id}{CLICK_SECRET_KEY}{merchant_trans_id}{amount}{action}{sign_time}"
    generated_signature = hashlib.md5(sign_string.encode('utf-8')).hexdigest()

    return generated_signature == signature

@app.route('/click/prepare', methods=['POST'])
def click_prepare():
    """Handle Click prepare request"""
    logger.info(f'Received Click prepare request: {request.form}')
    
    try:
        # Verify signature
        if not verify_click_signature(request.form, request.form.get('sign_string')):
            logger.warning('Invalid Click signature')
            return jsonify({
                'error': -1,
                'error_note': 'Invalid signature'
            })

        merchant_trans_id = request.form.get('merchant_trans_id')
        amount = float(request.form.get('amount', 0))
        
        # Extract user_id from merchant_trans_id (format: order_USER_ID_TIMESTAMP)
        try:
            user_id = int(merchant_trans_id.split('_')[1])
        except (IndexError, ValueError):
            logger.error(f'Invalid merchant_trans_id format: {merchant_trans_id}')
            return jsonify({
                'error': -1,
                'error_note': 'Invalid merchant transaction ID'
            })

        # Verify user exists
        user = get_user(user_id)
        if not user:
            return jsonify({
                'error': -1,
                'error_note': 'User not found'
            })

        # Calculate uses based on amount
        click = ClickIntegration()
        uses = click.calculate_uses(amount)

        return jsonify({
            'error': 0,
            'error_note': 'Success'
        })

    except Exception as e:
        logger.error(f'Error in Click prepare: {str(e)}')
        return jsonify({
            'error': -1,
            'error_note': 'System error'
        })

@app.route('/click/complete', methods=['POST'])
def click_complete():
    """Handle Click complete request"""
    logger.info(f'Received Click complete request: {request.form}')
    
    try:
        # Verify signature
        if not verify_click_signature(request.form, request.form.get('sign_string')):
            logger.warning('Invalid Click signature')
            return jsonify({
                'error': -1,
                'error_note': 'Invalid signature'
            })

        merchant_trans_id = request.form.get('merchant_trans_id')
        click_trans_id = request.form.get('click_trans_id')
        amount = float(request.form.get('amount', 0))
        
        # Extract user_id from merchant_trans_id
        try:
            user_id = int(merchant_trans_id.split('_')[1])
        except (IndexError, ValueError):
            logger.error(f'Invalid merchant_trans_id format: {merchant_trans_id}')
            return jsonify({
                'error': -1,
                'error_note': 'Invalid merchant transaction ID'
            })

        # Get transaction
        transaction = get_transaction_by_click_id(click_trans_id)
        if transaction:
            # Check if transaction is already completed
            if transaction['payment_state'] == TransactionState.PAID.value:
                return jsonify({
                    'error': 0,
                    'error_note': 'Transaction already completed'
                })
        
        # Calculate uses and add to user's account
        click = ClickIntegration()
        uses = click.calculate_uses(amount)
        add_purchased_uses(user_id, uses)
        
        # Update transaction status
        update_transaction_status(
            click_trans_id,
            TransactionState.PAID,
            perform_time=int(time.time() * 1000)
        )

        return jsonify({
            'error': 0,
            'error_note': 'Success'
        })

    except Exception as e:
        logger.error(f'Error in Click complete: {str(e)}')
        return jsonify({
            'error': -1,
            'error_note': 'System error'
        })

if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5000)