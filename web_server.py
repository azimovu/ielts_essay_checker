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
    create_transaction,
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
    """
    Verify Click API request signature.

    Parameters:
    - data (dict): The data received from Click API.
    - signature (str): The signature provided in the request.

    Returns:
    - bool: True if signature is valid, False otherwise.
    """
    try:
        click_trans_id = str(data.get('click_trans_id', ''))
        service_id = str(data.get('service_id', ''))
        merchant_trans_id = str(data.get('merchant_trans_id', ''))
        amount = str(data.get('amount', ''))
        action = str(data.get('action', ''))
        sign_time = str(data.get('sign_time', ''))

        if action == '1':  # Complete
            merchant_prepare_id = str(data.get('merchant_prepare_id', ''))
            sign_string = click_trans_id + service_id + CLICK_SECRET_KEY + merchant_trans_id + merchant_prepare_id + amount + action + sign_time
        else:  # Prepare
            sign_string = click_trans_id + service_id + CLICK_SECRET_KEY + merchant_trans_id + amount + action + sign_time

        generated_signature = hashlib.md5(sign_string.encode('utf-8')).hexdigest()
        return generated_signature.lower() == signature.lower()

    except Exception as e:
        logger.error(f"Error during signature verification: {e}")
        return False

@app.before_request
def log_request_info():
    logger.info('Headers: %s', dict(request.headers))
    logger.info('Body: %s', request.get_data().decode('utf-8'))
    logger.info('URL: %s', request.url)
    logger.info('Method: %s', request.method)

# Also add logging to catch any errors
@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
    return jsonify({
        'error': -1,
        'error_note': 'Internal server error'
    }), 500

@app.route('/click/prepare', methods=['POST'])
def click_prepare():
    try:
        data = request.form
        logger.info(f"Received Click prepare request: {data}")

        # 1. Verify signature
        sign_string = data.get('sign_string')
        sign_time = data.get('sign_time')
        click_trans_id = data.get('click_trans_id')
        service_id = data.get('service_id')
        merchant_trans_id = data.get('merchant_trans_id')
        amount = data.get('amount')
        action = data.get('action')

        # Generate sign string
        check_string = f"{click_trans_id}{service_id}{CLICK_SECRET_KEY}{merchant_trans_id}{amount}{action}{sign_time}"
        my_sign = hashlib.md5(check_string.encode('utf-8')).hexdigest()

        if my_sign != sign_string:
            logger.error(f"Sign string mismatch. Expected: {my_sign}, Got: {sign_string}")
            return jsonify({
                'error': -1,
                'error_note': 'SIGN CHECK FAILED!'
            })

        # 2. Get transaction from database
        transaction = get_transaction_by_click_id(merchant_trans_id)
        
        if not transaction:
            return jsonify({
                'error': -5,
                'error_note': 'Order not found'
            })

        # 3. Verify amount
        if float(amount) != float(transaction['amount']):
            return jsonify({
                'error': -2,
                'error_note': 'Incorrect amount'
            })

        # 4. Update transaction state
        update_transaction_status(
            transaction_id=merchant_trans_id,
            state=TransactionState.CREATED,
            is_click=True
        )

        # 5. Return successful response
        return jsonify({
            'click_trans_id': click_trans_id,
            'merchant_trans_id': merchant_trans_id,
            'merchant_prepare_id': transaction['id'],
            'error': 0,
            'error_note': 'Success'
        })

    except Exception as e:
        logger.error(f"Error in Click prepare: {str(e)}", exc_info=True)
        return jsonify({
            'error': -1,
            'error_note': f'Internal error: {str(e)}'
        })

@app.route('/click/complete', methods=['POST'])
def click_complete():
    try:
        data = request.form
        logger.info(f"Received Click complete request: {data}")

        # 1. Verify signature
        sign_string = data.get('sign_string')
        sign_time = data.get('sign_time')
        click_trans_id = data.get('click_trans_id')
        service_id = data.get('service_id')
        merchant_trans_id = data.get('merchant_trans_id')
        merchant_prepare_id = data.get('merchant_prepare_id')
        amount = data.get('amount')
        action = data.get('action')

        # Generate sign string
        check_string = f"{click_trans_id}{service_id}{CLICK_SECRET_KEY}{merchant_trans_id}{merchant_prepare_id}{amount}{action}{sign_time}"
        my_sign = hashlib.md5(check_string.encode('utf-8')).hexdigest()

        if my_sign != sign_string:
            logger.error(f"Sign string mismatch. Expected: {my_sign}, Got: {sign_string}")
            return jsonify({
                'error': -1,
                'error_note': 'SIGN CHECK FAILED!'
            })

        # 2. Get transaction
        transaction = get_transaction_by_click_id(merchant_trans_id)
        
        if not transaction:
            return jsonify({
                'error': -5,
                'error_note': 'Order not found'
            })

        # 3. Check if payment was already completed
        if transaction['payment_state'] == TransactionState.PAID.value:
            return jsonify({
                'error': -4,
                'error_note': 'Already paid'
            })

        # 4. Process the payment
        error = int(data.get('error', '-1'))
        if error == 0:
            # Successful payment
            update_transaction_status(
                transaction_id=merchant_trans_id,
                state=TransactionState.PAID,
                perform_time=int(time.time() * 1000),
                is_click=True
            )

            # Add purchased uses to user
            add_purchased_uses(
                transaction['user_id'],
                transaction['uses']
            )
        else:
            # Failed payment
            update_transaction_status(
                transaction_id=merchant_trans_id,
                state=TransactionState.CANCELLED,
                cancel_time=int(time.time() * 1000),
                reason=error,
                is_click=True
            )

        # 5. Return response
        return jsonify({
            'click_trans_id': click_trans_id,
            'merchant_trans_id': merchant_trans_id,
            'merchant_confirm_id': transaction['id'],
            'error': 0,
            'error_note': 'Success'
        })

    except Exception as e:
        logger.error(f"Error in Click complete: {str(e)}", exc_info=True)
        return jsonify({
            'error': -1,
            'error_note': f'Internal error: {str(e)}'
        })

if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5000)