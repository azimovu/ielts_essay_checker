from flask import Flask, request, jsonify
from config import CLICK_SECRET_KEY
import hashlib
from database import add_purchased_uses, get_user
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Create a file handler for logging
handler = RotatingFileHandler('flask_app.log', maxBytes=100000, backupCount=3)
handler.setLevel(logging.INFO)

# Create a formatter and set it for the handler
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(handler)

@app.route('/click/prepare', methods=['GET', 'POST'])
def prepare_payment():
    logger.info(f'Received {request.method} request to /click/prepare from {request.remote_addr}')
    logger.info(f'Request headers: {dict(request.headers)}')
    logger.info(f'Request form data: {request.form}')
    
    if request.method == 'POST':
        if not verify_click_request(request.form):
            logger.warning('Invalid signature for /click/prepare request')
            return jsonify({'error': -1, 'error_note': 'Invalid signature'})

        user_id = int(request.form['merchant_trans_id'])
        amount = float(request.form['amount'])
        user = get_user(user_id)

        if not user:
            logger.warning(f'User with ID {user_id} not found for /click/prepare request')
            return jsonify({'error': -5, 'error_note': 'User not found'})

        logger.info(f'Successfully processed /click/prepare request for user ID {user_id}')
        return jsonify({'error': 0, 'error_note': 'Success'})
    elif request.method == 'GET':
        logger.info('Received GET request to /click/prepare')
        return jsonify({'error': -1, 'error_note': 'GET method not supported for this endpoint'})

@app.route('/click/complete', methods=['GET', 'POST'])
def complete_payment():
    logger.info(f'Received {request.method} request to /click/complete from {request.remote_addr}')
    logger.info(f'Request headers: {dict(request.headers)}')
    logger.info(f'Request form data: {request.form}')
    
    if request.method == 'POST':
        if not verify_click_request(request.form):
            logger.warning('Invalid signature for /click/complete request')
            return jsonify({'error': -1, 'error_note': 'Invalid signature'})

        user_id = int(request.form['merchant_trans_id'])
        amount = float(request.form['amount'])
        uses = calculate_uses(amount)
        add_purchased_uses(user_id, uses)

        logger.info(f'Successfully processed /click/complete request for user ID {user_id} with {uses} uses')
        return jsonify({'error': 0, 'error_note': 'Success'})
    elif request.method == 'GET':
        logger.info('Received GET request to /click/complete')
        return jsonify({'error': -1, 'error_note': 'GET method not supported for this endpoint'})

def verify_click_request(form_data):
    received_sign = form_data['sign']
    sorted_keys = sorted(form_data.keys())
    sign_string = '|'.join([form_data[key] for key in sorted_keys if key != 'sign'])
    sign_string += f'|{CLICK_SECRET_KEY}'
    calculated_sign = hashlib.md5(sign_string.encode()).hexdigest()
    return received_sign == calculated_sign

def calculate_uses(amount):
    return int(amount // 10)  # Example implementation

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
