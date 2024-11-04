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
        logger.info(f"Headers: {request.headers}")
        logger.info(f"Body: {request.get_data(as_text=True)}")
        logger.info(f"URL: {request.url}")
        logger.info(f"Method: {request.method}")
        
        data = request.form
        logger.info(f"Received Click prepare request: {data}")

        # Validate required parameters
        required_params = ['click_trans_id', 'service_id', 'merchant_trans_id', 'amount']
        if not all(param in data for param in required_params):
            return jsonify({
                'error': -8,
                'error_note': 'Missing required parameters'
            })

        # Verify signature
        sign_string = data.get('sign_string')
        sign_time = data.get('sign_time')
        
        # Get transaction
        transaction = get_transaction_by_click_id(data['merchant_trans_id'])
        
        if not transaction:
            return jsonify({
                'error': -5,
                'error_note': 'Transaction not found'
            })

        # Verify amount
        if float(data['amount']) != float(transaction['amount']):
            return jsonify({
                'error': -2,
                'error_note': 'Incorrect amount'
            })

        return jsonify({
            'click_trans_id': data['click_trans_id'],
            'merchant_trans_id': data['merchant_trans_id'],
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
    logger.info(f'Received Click complete request: {request.form}')
    
    response = {
        'click_trans_id': request.form.get('click_trans_id'),
        'merchant_trans_id': request.form.get('merchant_trans_id'),
        'merchant_confirm_id': None,
        'error': -1,
        'error_note': ''
    }

    try:
        # Verify signature
        if not verify_click_signature(request.form, request.form.get('sign_string')):
            response['error'] = -1
            response['error_note'] = 'SIGN CHECK FAILED!'
            return jsonify(response)

        click_trans_id = request.form.get('click_trans_id')
        merchant_trans_id = request.form.get('merchant_trans_id')
        merchant_prepare_id = request.form.get('merchant_prepare_id')
        amount = request.form.get('amount')

        if not all([click_trans_id, merchant_trans_id, merchant_prepare_id, amount]):
            response['error'] = -8
            response['error_note'] = 'Error in request from click'
            return jsonify(response)

        # Get transaction
        transaction = get_transaction_by_click_id(click_trans_id)
        if not transaction:
            response['error'] = -6
            response['error_note'] = 'Transaction does not exist'
            return jsonify(response)

        # Check transaction state
        if transaction['payment_state'] == TransactionState.PAID.value:
            response['error'] = -4
            response['error_note'] = 'Already paid'
            return jsonify(response)
        elif transaction['payment_state'] == TransactionState.CANCELLED.value:
            response['error'] = -9
            response['error_note'] = 'Transaction cancelled'
            return jsonify(response)

        # Process payment
        try:
            user_id = int(merchant_trans_id.split('_')[1])
            click = ClickIntegration()
            uses = click.calculate_uses(float(amount))
            add_purchased_uses(user_id, uses)
            
            merchant_confirm_id = update_transaction_status(
                click_trans_id,
                TransactionState.PAID,
                perform_time=int(time.time() * 1000)
            )

            response['error'] = 0
            response['error_note'] = 'Success'
            response['merchant_confirm_id'] = merchant_confirm_id
            return jsonify(response)

        except Exception as e:
            logger.error(f'Error processing payment: {e}')
            response['error'] = -7
            response['error_note'] = 'Failed to update user'
            return jsonify(response)

    except Exception as e:
        logger.error(f'Error in Click complete: {str(e)}')
        response['error'] = -8
        response['error_note'] = 'Error in request from click'
        return jsonify(response)

if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5000)