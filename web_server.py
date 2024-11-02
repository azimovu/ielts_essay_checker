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

@app.route('/click/prepare', methods=['POST'])
def click_prepare():
    logger.info(f'Received Click prepare request: {request.form}')
    
    response = {
        'click_trans_id': request.form.get('click_trans_id'),
        'merchant_trans_id': request.form.get('merchant_trans_id'),
        'merchant_prepare_id': None,
        'error': -1,
        'error_note': ''
    }

    try:
        # Verify signature
        if not verify_click_signature(request.form, request.form.get('sign_string')):
            response['error'] = -1
            response['error_note'] = 'SIGN CHECK FAILED!'
            return jsonify(response)

        # Verify required parameters
        merchant_trans_id = request.form.get('merchant_trans_id')
        amount = request.form.get('amount')
        
        if not all([merchant_trans_id, amount]):
            response['error'] = -8
            response['error_note'] = 'Error in request from click'
            return jsonify(response)

        try:
            amount = float(amount)
        except ValueError:
            response['error'] = -2
            response['error_note'] = 'Incorrect parameter amount'
            return jsonify(response)

        # Extract user_id from merchant_trans_id
        try:
            user_id = int(merchant_trans_id.split('_')[1])
        except (IndexError, ValueError):
            response['error'] = -5
            response['error_note'] = 'User does not exist'
            return jsonify(response)

        # Verify user exists
        user = get_user(user_id)
        if not user:
            response['error'] = -5
            response['error_note'] = 'User does not exist'
            return jsonify(response)

        # Check if transaction already exists
        existing_transaction = get_transaction_by_click_id(request.form.get('click_trans_id'))
        if existing_transaction:
            if existing_transaction['payment_state'] == TransactionState.PAID.value:
                response['error'] = -4
                response['error_note'] = 'Already paid'
                return jsonify(response)
            elif existing_transaction['payment_state'] == TransactionState.CANCELLED.value:
                response['error'] = -9
                response['error_note'] = 'Transaction cancelled'
                return jsonify(response)

        # Create new transaction
        merchant_prepare_id = create_transaction(
            click_trans_id=request.form.get('click_trans_id'),
            merchant_trans_id=merchant_trans_id,
            amount=amount,
            state=TransactionState.WAITING
        )

        response['error'] = 0
        response['error_note'] = 'Success'
        response['merchant_prepare_id'] = merchant_prepare_id
        return jsonify(response)

    except Exception as e:
        logger.error(f'Error in Click prepare: {str(e)}')
        response['error'] = -8
        response['error_note'] = 'Error in request from click'
        return jsonify(response)

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